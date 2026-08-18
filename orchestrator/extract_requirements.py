"""
Stage 1 of the pipeline: turn a free-text problem statement into a
numbered list of discrete Requirement objects.
"""

from pydantic import BaseModel

from llm.base import LLMProvider
from schemas.requirement_analysis import Requirement


class RequirementList(BaseModel):
    """Wrapper so generate_structured has a single BaseModel to target."""

    requirements: list[Requirement]


def _build_prompt(problem_statement: str) -> str:
    return (
        "You are analyzing a software project problem statement. Break it "
        "down into a numbered list of discrete requirements.\n\n"
        "Rules:\n"
        "- Each requirement must be a single, atomic need — do not bundle "
        "multiple concerns into one requirement.\n"
        "- Assign each requirement a sequential id: R1, R2, R3, ...\n"
        "- Give each requirement a short category label, e.g. 'security', "
        "'scalability', 'developer velocity', 'maintainability'.\n"
        "- text should be a concise statement of the requirement itself, "
        "not a restatement of the whole problem statement.\n\n"
        f"PROBLEM STATEMENT:\n{problem_statement}"
    )


def extract_requirements(problem_statement: str, provider: LLMProvider) -> list[Requirement]:
    prompt = _build_prompt(problem_statement)
    result = provider.generate_structured(prompt, RequirementList)
    return result.requirements


if __name__ == "__main__":
    from llm.ollama_provider import OllamaProvider

    TEST_PROBLEM_STATEMENT = (
        "Build a backend for a high-traffic e-commerce platform that needs "
        "strong security, rapid development, and horizontal scalability."
    )

    requirements = extract_requirements(TEST_PROBLEM_STATEMENT, OllamaProvider())

    for req in requirements:
        print(f"{req.id} [{req.category}] {req.text}")
