"""
Abstract LLM interface. The orchestrator calls THIS, never a provider
SDK directly — that's what makes swapping Claude for a local model later
a one-file change instead of a rewrite.
"""

from abc import ABC, abstractmethod
from typing import Type, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProvider(ABC):
    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_schema: Type[SchemaT],
        max_retries: int = 2,
    ) -> SchemaT:
        """
        Send `prompt`, force the response to validate against
        `response_schema`. On validation failure, retry up to
        `max_retries` times. If it still fails, raise — never pass
        invalid data forward to the scorer.
        """
        raise NotImplementedError
