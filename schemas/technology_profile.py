"""
TechnologyProfile schema — the knowledge base record shape.

Locked fields (do not add more without a real reason — see conversation log):
    request_handling_model, typing, ecosystem_maturity, learning_curve,
    operational_complexity, horizontal_scaling, source_citations, last_reviewed

These are hand-curated by a human. The LLM never writes these — it only
reads and matches against them at inference time.
"""

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class RequestHandlingModel(str, Enum):
    SYNC = "sync"
    ASYNC = "async"
    HYBRID = "hybrid"


class Typing(str, Enum):
    STATIC = "static"
    DYNAMIC = "dynamic"


class EcosystemMaturity(str, Enum):
    NASCENT = "nascent"
    GROWING = "growing"
    MATURE = "mature"


class LearningCurve(str, Enum):
    """
    Always evaluated relative to a fixed baseline: a developer who
    already knows JavaScript. Do not re-baseline per technology.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class OperationalComplexity(str, Enum):
    """
    Assumes standard managed hosting for the technology (e.g. Vercel
    for Next.js). If that assumption matters, note it in
    source_citations rather than adding a hosting field.
    """

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class HorizontalScaling(str, Enum):
    NATIVE = "native"
    VIA_EXTENSION = "via-extension"
    DIFFICULT = "difficult"


class TechnologyProfile(BaseModel):
    id: str = Field(..., description="Stable slug, e.g. 'nextjs'")
    display_name: str
    department: str = Field(..., description="e.g. 'backend'")

    request_handling_model: RequestHandlingModel
    typing: Typing
    ecosystem_maturity: EcosystemMaturity
    learning_curve: LearningCurve
    operational_complexity: OperationalComplexity
    horizontal_scaling: HorizontalScaling

    source_citations: list[str] = Field(
        ..., description="URLs or references backing these judgments. Never empty."
    )
    notes: str | None = Field(
        default=None,
        description="Free-text caveats, e.g. 'typing is dynamic but TS is the "
        "ecosystem norm' or hosting assumptions. Never consumed by the scorer.",
    )
    last_reviewed: date

    class Config:
        use_enum_values = True
