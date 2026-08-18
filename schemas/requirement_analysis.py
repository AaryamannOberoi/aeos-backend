"""
RequirementAnalysis — the schema-validated shape the LLM outputs.

Hard rule (§36.2 of the architecture doc): zero numeric or scalar fields.
If the LLM emits a score/confidence number here, that response must be
REJECTED at parse time and re-generated. This isn't a style guideline.

reasoning is free text and is NEVER read by the scorer — it's for the
human/UI only.
"""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from schemas.technology_profile import (
    EcosystemMaturity,
    HorizontalScaling,
    LearningCurve,
    OperationalComplexity,
    RequestHandlingModel,
    Typing,
)


class ImpliedAttributeNeeds(BaseModel):
    """
    What the requirement implies about the ideal technology, expressed
    using the SAME enums as TechnologyProfile so the scorer can compare
    like-for-like. Every field optional — a requirement doesn't have to
    imply an opinion on every attribute.
    """

    request_handling_model: RequestHandlingModel | None = None
    typing: Typing | None = None
    ecosystem_maturity: EcosystemMaturity | None = None
    learning_curve: LearningCurve | None = None
    operational_complexity: OperationalComplexity | None = None
    horizontal_scaling: HorizontalScaling | None = None


class Requirement(BaseModel):
    """Output of stage 1: requirement extraction."""

    id: str = Field(..., description="e.g. 'R1'")
    text: str
    category: str = Field(..., description="e.g. 'scalability', 'security'")


class ConstraintType(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class Constraint(BaseModel):
    """Output of stage 2: constraint extraction."""

    id: str
    text: str
    type: ConstraintType


class RequirementAnalysis(BaseModel):
    """Output of stage 3: discipline analysis, per requirement."""

    requirement_id: str
    implied_attribute_needs: ImpliedAttributeNeeds
    supporting_evidence: list[str] = Field(
        ..., description="kb_ref ids, or ['NO_EVIDENCE_FOUND'] — never empty"
    )
    reasoning: str = Field(
        ..., description="Free text narrative only. NEVER consumed by the scorer."
    )

    model_config = ConfigDict(use_enum_values=True)
