"""Gemini structured extraction adapter for the provider-neutral interview engine."""

import json
from typing import Literal

import httpx
from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError

from app.ai.interview.schemas import ClinicalField, ClinicalState, Extraction, Fact, NextQuestion
from app.ai.llm.client import ProviderError
from app.ai.llm.prompts import EXTRACTION_PROMPT

BOOLEAN_FIELDS = {"breathlessness", "cough", "sudden_onset", "vomiting"}
LIST_FIELDS = {
    "past_medical_history",
    "medications",
    "allergies",
    "family_history",
    "personal_history",
}


class GeminiFactPayload(BaseModel):
    """Gemini-safe wire shape; avoids a five-type union in a single property."""

    field: ClinicalField
    status: Literal["reported", "unknown", "declined"]
    text_value: str | None = None
    integer_value: int | None = None
    boolean_value: bool | None = None
    list_value: list[str] | None = None
    evidence: str

    def to_fact(self) -> Fact:
        values = {
            "text_value": self.text_value,
            "integer_value": self.integer_value,
            "boolean_value": self.boolean_value,
            "list_value": self.list_value,
        }
        populated = [name for name, value in values.items() if value is not None]

        if self.status == "reported":
            if self.field == "severity":
                expected = "integer_value"
            elif self.field in BOOLEAN_FIELDS:
                expected = "boolean_value"
            elif self.field in LIST_FIELDS:
                expected = "list_value"
            else:
                expected = "text_value"
            if populated != [expected]:
                raise ValueError(f"Reported {self.field} must use only the {expected} slot")
            value = values[expected]
        else:
            if self.status not in {"unknown", "declined"} or populated:
                raise ValueError("Unknown or declined facts cannot contain a value")
            value = None

        return Fact(
            field=self.field,
            value=value,
            status=self.status,
            evidence=self.evidence,
        )


class GeminiExtractionPayload(BaseModel):
    """Provider-only schema converted into the stable public Extraction contract."""

    facts: list[GeminiFactPayload] = Field(default_factory=list)
    uncertain_fields: list[ClinicalField] = Field(default_factory=list)

    def to_extraction(self) -> Extraction:
        return Extraction(
            facts=[fact.to_fact() for fact in self.facts],
            uncertain_fields=self.uncertain_fields,
        )


class GeminiProvider:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        timeout: float = 30,
        client=None,
    ):
        if not api_key or not model:
            raise ValueError("GEMINI_API_KEY and GEMINI_MODEL are required for gemini mode")
        self.model = model
        self.client = client or genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(timeout * 1000)),
        )

    def extract(self, statement: str, question: NextQuestion, state: ClinicalState) -> Extraction:
        payload = {
            "statement": statement,
            "question": question.model_dump(),
            "clinical_state": state.model_dump(),
        }
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=json.dumps(payload, ensure_ascii=False),
                config=types.GenerateContentConfig(
                    system_instruction=EXTRACTION_PROMPT,
                    response_mime_type="application/json",
                    response_schema=GeminiExtractionPayload,
                    temperature=0,
                    max_output_tokens=2500,
                ),
            )
            parsed = getattr(response, "parsed", None)
            if parsed is not None:
                if isinstance(parsed, Extraction):
                    return parsed
                return GeminiExtractionPayload.model_validate(parsed).to_extraction()
            text = getattr(response, "text", None)
            if not text:
                raise ProviderError(
                    "Gemini returned an empty or blocked extraction. Please retry.",
                    code="incomplete_response",
                )
            return GeminiExtractionPayload.model_validate_json(text).to_extraction()
        except ProviderError:
            raise
        except errors.APIError as exc:
            status = getattr(exc, "code", None)
            if status == 400:
                message = "Gemini rejected the structured extraction request."
                code = "invalid_provider_request"
            elif status == 401:
                message = "Gemini rejected the API key. Create a valid Google AI Studio key."
                code = "authentication_failed"
            elif status == 403:
                message = (
                    "This Gemini API key does not have permission to use the configured model."
                )
                code = "permission_denied"
            elif status == 404:
                message = "The configured Gemini model was not found or is unavailable."
                code = "model_unavailable"
            elif status == 429:
                message = "Gemini free-tier or project rate limit reached. Wait and retry."
                code = "rate_limited"
            elif status in {408, 504}:
                message = "Gemini did not respond before the timeout."
                code = "provider_timeout"
            elif isinstance(status, int) and status >= 500:
                message = "Gemini is temporarily unavailable. Retry shortly."
                code = "provider_unavailable"
            else:
                message = "Gemini could not complete the extraction request."
                code = "provider_error"
            raise ProviderError(message, code=code) from exc
        except (httpx.TimeoutException, TimeoutError) as exc:
            raise ProviderError(
                "Gemini did not respond before the timeout.", code="provider_timeout"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(
                "The backend could not connect to Gemini.", code="provider_unavailable"
            ) from exc
        except (ValidationError, ValueError) as exc:
            raise ProviderError(
                "Gemini returned data that did not match the clinical extraction contract.",
                code="invalid_provider_output",
            ) from exc
