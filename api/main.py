"""
Thin HTTP wrapper around orchestrator.pipeline.run_backend_pipeline.
No auth, no endpoints beyond /analyze and /health — deliberately.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel

from orchestrator.pipeline import _ATTRIBUTE_ENUMS, run_backend_pipeline

# The six TechnologyProfile fields that run_backend_pipeline / scorer.py
# score against — same set orchestrator/pipeline.py's own __main__ uses
# to build its equal-weight test runs.
DEFAULT_AXES = list(_ATTRIBUTE_ENUMS.keys())

app = FastAPI()


class AnalyzeRequest(BaseModel):
    problem_statement: str
    weights: dict[str, float] | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/analyze")
def analyze(request: AnalyzeRequest) -> dict:
    weights = request.weights
    if weights is None:
        weights = {axis: 1.0 for axis in DEFAULT_AXES}

    return run_backend_pipeline(request.problem_statement, weights)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
