"""
Integration step: wires stages 1-4 (requirement extraction, constraint
extraction, requirement analysis, scoring) into one end-to-end run
against the backend knowledge base.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from knowledge_base.loader import load_department
from llm.base import LLMProvider
from llm.ollama_provider import OllamaProvider
from orchestrator.analyze_backend import analyze_all
from orchestrator.extract_constraints import extract_constraints
from orchestrator.extract_requirements import extract_requirements
from schemas.requirement_analysis import Constraint, ConstraintType, Requirement, RequirementAnalysis
from schemas.technology_profile import (
    EcosystemMaturity,
    HorizontalScaling,
    LearningCurve,
    OperationalComplexity,
    RequestHandlingModel,
    TechnologyProfile,
    Typing,
)
from scoring.scorer import rank_candidates

_ATTRIBUTE_ENUMS: dict[str, type] = {
    "request_handling_model": RequestHandlingModel,
    "typing": Typing,
    "ecosystem_maturity": EcosystemMaturity,
    "learning_curve": LearningCurve,
    "operational_complexity": OperationalComplexity,
    "horizontal_scaling": HorizontalScaling,
}

# Plain-English label that must literally appear in a constraint's text
# before we'll even consider mapping it to this field. This is the
# precision half of the "don't guess" rule: field label match alone
# isn't enough (see _checkable_requirement), but without it a bare enum
# value like "static" or "low" could match on the wrong axis, or match
# coincidentally in unrelated prose.
_FIELD_LABELS: dict[str, str] = {
    "request_handling_model": "request handling",
    "typing": "typing",
    "ecosystem_maturity": "ecosystem",
    "learning_curve": "learning curve",
    "operational_complexity": "operational complexity",
    "horizontal_scaling": "horizontal scal",  # matches scaling/scalable/scalability
}


def _value_mentioned(value: str, text: str) -> bool:
    token = re.escape(value).replace(r"\-", "[-_ ]")
    return re.search(rf"\b{token}\b", text, re.IGNORECASE) is not None


def _checkable_requirement(constraint: Constraint) -> tuple[str, str] | None:
    """
    Best-effort, deterministic (no LLM) read of a hard constraint as
    "field X must equal value Y". Only returns a match when BOTH the
    field's label phrase AND one of its enum values literally appear in
    the constraint text. That's a narrow, precise signal chosen
    specifically so this never has to guess at looser paraphrasing —
    if the text doesn't contain both, we don't know, so we don't act.
    """
    for field, label in _FIELD_LABELS.items():
        if label not in constraint.text.lower():
            continue
        for member in _ATTRIBUTE_ENUMS[field]:
            if _value_mentioned(member.value, constraint.text):
                return field, member.value
    return None


def eliminate_ineligible_profiles(
    profiles: list[TechnologyProfile], constraints: list[Constraint]
) -> tuple[list[TechnologyProfile], list[dict], list[str]]:
    """
    Plain Python, no LLM. For each HARD constraint, try to read it as a
    concrete requirement on one TechnologyProfile field via
    `_checkable_requirement`. Eliminate any profile whose actual value
    on that field doesn't match. If a hard constraint's text can't be
    mapped to a schema field with confidence, no profile is eliminated
    because of it — its id is returned separately so the caller can
    surface "this hard constraint was not checked" rather than silently
    dropping it.

    Returns (survivors, eliminated, unchecked_hard_constraint_ids).
    """
    eliminated: dict[str, dict] = {}
    unchecked: list[str] = []

    for constraint in constraints:
        if constraint.type != ConstraintType.HARD:
            continue

        match = _checkable_requirement(constraint)
        if match is None:
            unchecked.append(constraint.id)
            continue

        field, required_value = match
        for profile in profiles:
            actual_value = getattr(profile, field)
            if actual_value != required_value and profile.id not in eliminated:
                eliminated[profile.id] = {
                    "profile_id": profile.id,
                    "constraint_id": constraint.id,
                    "reason": (
                        f"constraint {constraint.id} ({constraint.text!r}) requires "
                        f"{field} == {required_value!r}, but {profile.id}.{field} == "
                        f"{actual_value!r}"
                    ),
                }

    survivors = [profile for profile in profiles if profile.id not in eliminated]
    return survivors, list(eliminated.values()), unchecked


_extraction_cache: dict[str, dict] = {}


def get_or_extract(problem_statement: str, provider: LLMProvider) -> dict:
    """
    Runs requirement extraction, constraint extraction, and requirement
    analysis for `problem_statement` exactly once, then caches the
    result in-process keyed by the problem statement text. Repeated
    calls with the same problem statement return the cached data
    instead of re-querying the LLM — this is what makes it possible to
    score the same extracted data under different weight configurations
    without the LLM's non-determinism confounding the comparison.

    Returns {"requirements": ..., "constraints": ..., "requirement_analyses": ...}.
    """
    if problem_statement in _extraction_cache:
        return _extraction_cache[problem_statement]

    requirements = extract_requirements(problem_statement, provider)
    constraints = extract_constraints(problem_statement, provider)
    requirement_analyses = analyze_all(requirements, provider)

    extracted = {
        "requirements": requirements,
        "constraints": constraints,
        "requirement_analyses": requirement_analyses,
    }
    _extraction_cache[problem_statement] = extracted
    return extracted


def run_backend_pipeline(
    problem_statement: str,
    weights: dict[str, float],
    *,
    requirements: list[Requirement] | None = None,
    constraints: list[Constraint] | None = None,
    requirement_analyses: list[RequirementAnalysis] | None = None,
) -> dict:
    """
    If `requirements`, `constraints`, and `requirement_analyses` are all
    supplied, no LLM call happens at all — the given data is scored
    as-is. If any are omitted, the missing piece(s) come from
    `get_or_extract`'s cache for `problem_statement` (extracting via the
    LLM only on the first call for a given problem statement).

    Passing all three explicitly lets a caller run a controlled
    comparison: extract once, then call this twice with different
    `weights` and identical requirements/constraints/analyses, so any
    difference in the ranking is attributable to the weights alone.
    """
    if requirements is None or constraints is None or requirement_analyses is None:
        extracted = get_or_extract(problem_statement, OllamaProvider())
        if requirements is None:
            requirements = extracted["requirements"]
        if constraints is None:
            constraints = extracted["constraints"]
        if requirement_analyses is None:
            requirement_analyses = extracted["requirement_analyses"]

    all_profiles = load_department("backend")
    survivors, eliminated, unchecked_hard_constraints = eliminate_ineligible_profiles(
        all_profiles, constraints
    )

    ranked_candidates = rank_candidates(survivors, requirement_analyses, weights)

    return {
        "requirements": requirements,
        "constraints": constraints,
        "ranked_candidates": ranked_candidates,
        "eliminated": eliminated,
        "unchecked_hard_constraints": unchecked_hard_constraints,
    }


def _print_pipeline_result(problem_statement: str, result: dict) -> None:
    print(f"##### {problem_statement} #####\n")

    print("=== Requirements ===")
    for req in result["requirements"]:
        print(f"  {req.id} [{req.category}] {req.text}")

    print("\n=== Constraints ===")
    for con in result["constraints"]:
        print(f"  {con.id} [{con.type.value}] {con.text}")

    print("\n=== Eliminated Candidates ===")
    if not result["eliminated"]:
        print("  (none)")
    else:
        for entry in result["eliminated"]:
            print(f"  {entry['profile_id']}: {entry['reason']}")

    if result["unchecked_hard_constraints"]:
        print("\n=== Hard Constraints Not Checkable Against Current Schema ===")
        for constraint_id in result["unchecked_hard_constraints"]:
            print(f"  {constraint_id}: could not be mapped to a TechnologyProfile "
                  f"field with confidence — skipped elimination rather than guess")

    print("\n=== Final Ranking ===")
    for rank, entry in enumerate(result["ranked_candidates"], start=1):
        print(f"  {rank}. {entry['profile_id']} — total={entry['total']:.3f}")
        print(f"     {entry['formula_trace']}")


if __name__ == "__main__":
    axes = list(_ATTRIBUTE_ENUMS.keys())
    equal_weights = {axis: round(1.0 / len(axes), 4) for axis in axes}

    ECOMMERCE_PROBLEM_STATEMENT = (
        "Build a backend for a high-traffic e-commerce platform that needs "
        "strong security, rapid development, and horizontal scalability."
    )
    ecommerce_result = run_backend_pipeline(ECOMMERCE_PROBLEM_STATEMENT, equal_weights)
    _print_pipeline_result(ECOMMERCE_PROBLEM_STATEMENT, ecommerce_result)

    INTERNAL_TOOL_PROBLEM_STATEMENT = (
        "A small internal tool for 50 employees, prioritize fast "
        "development over scale."
    )
    internal_tool_result = run_backend_pipeline(INTERNAL_TOOL_PROBLEM_STATEMENT, equal_weights)
    print("\n")
    _print_pipeline_result(INTERNAL_TOOL_PROBLEM_STATEMENT, internal_tool_result)

    # Run 3: a CONTROLLED comparison. Extract once for the e-commerce
    # problem statement, then score that identical requirements/
    # constraints/analyses data twice — once with equal weights, once
    # with learning_curve weighted 3x — so any ranking difference is
    # attributable to the weights alone, not to re-extraction variance.
    extracted = get_or_extract(ECOMMERCE_PROBLEM_STATEMENT, OllamaProvider())

    learning_curve_weights = {axis: 1.0 for axis in axes}
    learning_curve_weights["learning_curve"] = 3.0

    controlled_equal_result = run_backend_pipeline(
        ECOMMERCE_PROBLEM_STATEMENT,
        equal_weights,
        requirements=extracted["requirements"],
        constraints=extracted["constraints"],
        requirement_analyses=extracted["requirement_analyses"],
    )
    controlled_weighted_result = run_backend_pipeline(
        ECOMMERCE_PROBLEM_STATEMENT,
        learning_curve_weights,
        requirements=extracted["requirements"],
        constraints=extracted["constraints"],
        requirement_analyses=extracted["requirement_analyses"],
    )

    print("\n")
    print(f"##### CONTROLLED COMPARISON — {ECOMMERCE_PROBLEM_STATEMENT} #####")
    print("(identical extracted requirements/constraints/analyses used for both scorings)\n")

    print("=== Ranking A: equal weights ===")
    for rank, entry in enumerate(controlled_equal_result["ranked_candidates"], start=1):
        print(f"  {rank}. {entry['profile_id']} — total={entry['total']:.3f}")
        print(f"     {entry['formula_trace']}")

    print("\n=== Ranking B: learning_curve weight=3.0, all other axes=1.0 ===")
    for rank, entry in enumerate(controlled_weighted_result["ranked_candidates"], start=1):
        print(f"  {rank}. {entry['profile_id']} — total={entry['total']:.3f}")
        print(f"     {entry['formula_trace']}")

    order_a = [entry["profile_id"] for entry in controlled_equal_result["ranked_candidates"]]
    order_b = [entry["profile_id"] for entry in controlled_weighted_result["ranked_candidates"]]

    print("\n=== Comparison: Ranking A vs Ranking B ===")
    print(f"  Ranking A order: {order_a}")
    print(f"  Ranking B order: {order_b}")
    print(f"  Order {'UNCHANGED' if order_a == order_b else 'CHANGED'}.")
