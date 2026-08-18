"""
Ollama implementation of LLMProvider. This is the ONLY file that should
ever talk to a local Ollama instance. Everything else talks to
llm.base.LLMProvider.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Type

from pydantic import ValidationError

from llm.base import LLMProvider, SchemaT

# Model must already be pulled locally (`ollama pull llama3.1`). Swap here,
# nowhere else, if that changes.
MODEL = "llama3.1"

DEFAULT_BASE_URL = "http://localhost:11434"


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str | None = None, model: str = MODEL):
        self.base_url = (base_url or os.environ.get("OLLAMA_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.model = model

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[SchemaT],
        max_retries: int = 2,
    ) -> SchemaT:
        schema = response_schema.model_json_schema()
        schema_json = json.dumps(schema, indent=2)

        system = (
            "You output ONLY a single JSON object matching this JSON Schema. "
            "No prose, no markdown fences, no explanation outside the JSON. "
            "If a field is an enum, you MUST use one of the listed enum values "
            "exactly. Never invent a numeric 'score' or 'confidence' field "
            "unless the schema explicitly defines one.\n\n"
            f"SCHEMA:\n{schema_json}"
        )

        last_error: Exception | None = None
        for attempt in range(max_retries + 1):
            raw = self._chat(system=system, prompt=prompt, schema=schema).strip()
            try:
                return response_schema.model_validate_json(raw)
            except ValidationError as e:
                last_error = e
                prompt = (
                    f"{prompt}\n\nYour previous response failed schema "
                    f"validation with this error:\n{e}\nReturn ONLY corrected JSON."
                )

        raise RuntimeError(
            f"LLM failed to produce schema-valid output after {max_retries + 1} "
            f"attempts. Last error: {last_error}"
        )

    def _chat(self, system: str, prompt: str, schema: dict) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                "format": schema,
                "stream": False,
            }
        ).encode("utf-8")

        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Could not reach Ollama at {self.base_url}. Is `ollama serve` "
                f"running and has `{self.model}` been pulled? ({e})"
            ) from e

        return payload["message"]["content"]
