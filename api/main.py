"""
Thin HTTP wrapper around orchestrator.pipeline.run_backend_pipeline.
No auth, no endpoints beyond /analyze and /health — deliberately.
"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from orchestrator.pipeline import _ATTRIBUTE_ENUMS, run_backend_pipeline
from persistence.firestore_client import save_run

# The six TechnologyProfile fields that run_backend_pipeline / scorer.py
# score against — same set orchestrator/pipeline.py's own __main__ uses
# to build its equal-weight test runs.
DEFAULT_AXES = list(_ATTRIBUTE_ENUMS.keys())

logger = logging.getLogger(__name__)

app = FastAPI()


def _format_validation_errors(exc: ValidationError) -> list[dict]:
    """Strips pydantic's error objects down to field + message — no
    internal file paths or raw input echoed back to the client."""
    formatted = []
    for err in exc.errors():
        field = ".".join(str(part) for part in err.get("loc", ())) or "(root)"
        formatted.append({"field": field, "message": err.get("msg", "Invalid value")})
    return formatted


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
    """A pydantic ValidationError raised anywhere in the pipeline (e.g.
    malformed data reaching a schema) — client-side problem, so 422."""
    logger.warning("Validation error on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=422,
        content={"error": "Validation failed", "details": _format_validation_errors(exc)},
    )


@app.exception_handler(RuntimeError)
async def llm_failure_handler(request: Request, exc: RuntimeError) -> JSONResponse:
    """llm/ollama_provider.py (and llm/claude_provider.py) raise plain
    RuntimeError both when the backing service is unreachable and when
    the LLM never produces schema-valid output after retries. Neither
    is the caller's fault, so 502."""
    logger.error("LLM/Ollama failure on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=502,
        content={"error": "AI extraction failed, please retry"},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log the full traceback server-side, never echo it —
    the response body must never carry stack traces, file paths, or
    API keys."""
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error. Please try again later."},
    )


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

    result = run_backend_pipeline(request.problem_statement, weights)
    result = jsonable_encoder(result)

    run_id = save_run(request.problem_statement, weights, result)
    result["run_id"] = run_id

    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
