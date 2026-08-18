"""
Stage 4 of the pipeline: score each candidate TechnologyProfile against
the RequirementAnalysis list produced in stage 3, and rank candidates.

Plain Python only — NO LLM CALLS ANYWHERE IN THIS FILE. Every input here
is already-validated, already-generated data; this module just does
arithmetic on it.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schemas.requirement_analysis import RequirementAnalysis
from schemas.technology_profile import TechnologyProfile

# ENUM_WEIGHTS: a fixed "how desirable is this value in general" scale
# for every enum value used in TechnologyProfile, 0.0 (worst) to 1.0
# (best). This is ONE flat dict keyed by the raw string value (these are
# all `str, Enum` subclasses, so the string value IS the enum member for
# hashing/equality purposes).
#
# LearningCurve and OperationalComplexity happen to share the exact
# string set {low, medium, high}, and both use it in the same sense
# (low is good, high is bad) — so sharing entries for those two fields
# is deliberate, not a collision bug.
#
# Reasoning per axis:
# - request_handling_model: async handles concurrent I/O-bound load
#   without blocking a worker per request, which is what "scalability"
#   / "high traffic" requirements are usually asking for. hybrid gets
#   some of that flexibility without being fully optimized for it. sync
#   blocks a thread/process per request and is weakest under concurrent
#   load.
# - typing: static catches a class of bugs at compile time and scales
#   better with team/codebase size — the property most requirements are
#   gesturing at when they care about typing. dynamic trades that away
#   for faster prototyping.
# - ecosystem_maturity: mature means a large community, more prebuilt
#   solutions, fewer production surprises. growing is a credible middle
#   ground. nascent carries real production risk.
# - learning_curve / operational_complexity (shared scale): low is
#   unambiguously good on both (fast onboarding; few moving parts to
#   break). high is unambiguously costly on both. medium sits between.
# - horizontal_scaling: native means the framework/runtime scales out
#   of the box. via-extension means it's achievable but needs extra
#   infrastructure/config. difficult means it actively fights you.
ENUM_WEIGHTS: dict[str, float] = {
    # RequestHandlingModel
    "sync": 0.2,
    "async": 1.0,
    "hybrid": 0.7,
    # Typing
    "static": 1.0,
    "dynamic": 0.5,
    # EcosystemMaturity
    "nascent": 0.2,
    "growing": 0.6,
    "mature": 1.0,
    # LearningCurve / OperationalComplexity (shared: low=good, high=bad)
    "low": 1.0,
    "medium": 0.5,
    "high": 0.1,
    # HorizontalScaling
    "native": 1.0,
    "via-extension": 0.6,
    "difficult": 0.2,
}


def compute_axis_score(
    profile: TechnologyProfile, needs: list[RequirementAnalysis], axis: str
) -> float:
    """
    Average, over every RequirementAnalysis that expressed an opinion on
    `axis` (a TechnologyProfile field name, e.g. "horizontal_scaling"),
    of how well `profile`'s actual value for that axis matches the value
    the requirement implied was ideal.

    Match quality for one opinion is:
        1 - abs(ENUM_WEIGHTS[actual] - ENUM_WEIGHTS[ideal])
    so an exact match scores 1.0, and values further apart on the
    ENUM_WEIGHTS scale score lower — in both directions. Falling short
    of what was asked for AND overshooting it both count against a
    perfect match, because this axis is measuring fit to the stated
    need, not raw quality.

    If nothing in `needs` expressed an opinion on this axis, there's
    nothing to judge the profile against, so this returns 1.0 (neutral —
    no evidence, no penalty).
    """
    actual_value = getattr(profile, axis)
    actual_weight = ENUM_WEIGHTS[actual_value]

    implied_values = [
        implied
        for need in needs
        if (implied := getattr(need.implied_attribute_needs, axis)) is not None
    ]
    if not implied_values:
        return 1.0

    match_scores = [1 - abs(actual_weight - ENUM_WEIGHTS[ideal]) for ideal in implied_values]
    return sum(match_scores) / len(match_scores)


def score_candidate(
    profile: TechnologyProfile,
    needs: list[RequirementAnalysis],
    weights: dict[str, float],
) -> dict:
    """
    weights maps axis name (a TechnologyProfile field name) to how much
    that axis counts toward the total. Weights need not sum to 1.0 —
    total is simply the weighted sum of axis scores.

    Returns {"total": float, "sub_scores": dict[axis, float],
    "formula_trace": str} where formula_trace shows the literal
    arithmetic, e.g. "0.4*0.9 (horizontal_scaling) + 0.3*1.0 (typing)".
    """
    sub_scores: dict[str, float] = {}
    trace_terms: list[str] = []

    for axis, weight in weights.items():
        axis_score = compute_axis_score(profile, needs, axis)
        sub_scores[axis] = axis_score
        trace_terms.append(f"{weight}*{round(axis_score, 2)} ({axis})")

    total = sum(weights[axis] * sub_scores[axis] for axis in weights)

    return {
        "total": total,
        "sub_scores": sub_scores,
        "formula_trace": " + ".join(trace_terms),
    }


def rank_candidates(
    profiles: list[TechnologyProfile],
    needs: list[RequirementAnalysis],
    weights: dict[str, float],
) -> list[dict]:
    """Score every profile and return them sorted descending by total."""
    scored = [
        {"profile_id": profile.id, **score_candidate(profile, needs, weights)}
        for profile in profiles
    ]
    return sorted(scored, key=lambda entry: entry["total"], reverse=True)
