"""
Claude implementation of LLMProvider. This is the ONLY file that should
ever import the anthropic SDK. Everything else talks to llm.base.LLMProvider.
"""

import json
import os
from typing import Type

import anthropic
from pydantic import ValidationError

from llm.base import LLMProvider, SchemaT

# Cheapest model for MVP build/test. Swap here, nowhere else, if that changes.
MODEL = "claude-haiku-4-5-20251001"


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ["ANTHROPIC_API_KEY"])

    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[SchemaT],
        max_retries: int = 2,
    ) -> SchemaT:
        schema_json = json.dumps(response_schema.model_json_schema(), indent=2)

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
            message = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
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
