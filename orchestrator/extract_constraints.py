"""
Stage 2 of the pipeline: turn a free-text problem statement into a
numbered list of discrete Constraint objects, each classified hard or soft.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel

from llm.base import LLMProvider
from schemas.requirement_analysis import Constraint


class ConstraintList(BaseModel):
    """Wrapper so generate_structured has a single BaseModel to target."""

    constraints: list[Constraint]


def _build_prompt(problem_statement: str) -> str:
    return (
        "You are analyzing a software project problem statement. Break it "
        "down into a numbered list of discrete constraints.\n\n"
        "Rules:\n"
        "- Each constraint must be a single, atomic restriction — do not "
        "bundle multiple concerns into one constraint.\n"
        "- Assign each constraint a sequential id: C1, C2, C3, ...\n"
        "- Classify each constraint's type as 'hard' or 'soft': hard means "
        "the constraint is non-negotiable (e.g. a legal, budget, or "
        "existing-infrastructure requirement); soft means it is a "
        "preference that can be traded off against other concerns.\n"
        "- text should be a concise statement of the constraint itself, "
        "not a restatement of the whole problem statement.\n\n"
        f"PROBLEM STATEMENT:\n{problem_statement}"
    )


def extract_constraints(problem_statement: str, provider: LLMProvider) -> list[Constraint]:
    prompt = _build_prompt(problem_statement)
    result = provider.generate_structured(prompt, ConstraintList)
    return result.constraints


if __name__ == "__main__":
    from llm.ollama_provider import OllamaProvider
    from orchestrator.extract_requirements import extract_requirements

    TEST_PROBLEM_STATEMENT = (
        "Build a backend for a high-traffic e-commerce platform that needs "
        "strong security, rapid development, and horizontal scalability."
    )

    provider = OllamaProvider()

    requirements = extract_requirements(TEST_PROBLEM_STATEMENT, provider)
    constraints = extract_constraints(TEST_PROBLEM_STATEMENT, provider)

    print("Requirements:")
    for req in requirements:
        print(f"  {req.id} [{req.category}] {req.text}")

    print("Constraints:")
    for con in constraints:
        print(f"  {con.id} [{con.type.value}] {con.text}")
