"""
Stage 3 of the pipeline: for each extracted requirement, work out which
TechnologyProfile attributes it implies an opinion on.
"""

from knowledge_base.loader import load_department
from llm.base import LLMProvider
from schemas.requirement_analysis import Requirement, RequirementAnalysis


def _known_kb_refs() -> list[str]:
    return [profile.id for profile in load_department("backend")]


def _build_prompt(requirement: Requirement, kb_refs: list[str]) -> str:
    return (
        "You are analyzing ONE software requirement to work out what it "
        "implies about the ideal backend technology, using a fixed set of "
        "attributes.\n\n"
        "Rules:\n"
        "- Only set an attribute field in implied_attribute_needs if this "
        "requirement gives you a real opinion on it. If the requirement "
        "says nothing relevant to an attribute, leave that field null — "
        "do not guess just to fill every field.\n"
        f"- requirement_id must be exactly: {requirement.id}\n"
        "- supporting_evidence must be a list of kb_ref ids drawn ONLY "
        f"from this known set: {kb_refs}. Cite an id only if that "
        "technology's known profile genuinely illustrates or supports the "
        "attribute value you chose. If none apply, supporting_evidence "
        "must be exactly ['NO_EVIDENCE_FOUND'] — never empty.\n"
        "- reasoning is free text explaining your judgment for a human "
        "reader. It is never read by the scorer, but should be honest and "
        "specific about why you chose (or didn't choose) each attribute.\n\n"
        f"REQUIREMENT:\n[{requirement.id}] ({requirement.category}) {requirement.text}"
    )


def analyze_requirement(requirement: Requirement, provider: LLMProvider) -> RequirementAnalysis:
    prompt = _build_prompt(requirement, _known_kb_refs())
    result = provider.generate_structured(prompt, RequirementAnalysis)
    result.requirement_id = requirement.id
    return result


def analyze_all(requirements: list[Requirement], provider: LLMProvider) -> list[RequirementAnalysis]:
    return [analyze_requirement(requirement, provider) for requirement in requirements]


if __name__ == "__main__":
    from llm.ollama_provider import OllamaProvider
    from orchestrator.extract_requirements import extract_requirements

    TEST_PROBLEM_STATEMENT = (
        "Build a backend for a high-traffic e-commerce platform that needs "
        "strong security, rapid development, and horizontal scalability."
    )

    provider = OllamaProvider()

    requirements = extract_requirements(TEST_PROBLEM_STATEMENT, provider)
    analyses = analyze_all(requirements, provider)

    for analysis in analyses:
        print(analysis)
