from typing import Protocol

from app.interview.schemas import ClinicalState, Extraction, NextQuestion


class ProviderError(RuntimeError):
    """Sanitized external-provider failure; never contains patient text or secrets."""

    def __init__(
        self, message: str, *, code: str = "provider_error", request_id: str | None = None
    ):
        super().__init__(message)
        self.code = code
        self.request_id = request_id


class LLMClient(Protocol):
    def extract(self, statement: str, question: NextQuestion, state: ClinicalState) -> Extraction:
        """Extract only facts supported by the current statement and question context."""
        ...
