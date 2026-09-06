import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.interview.graph import OPENING, QuestionGraph
from app.interview.schemas import ClinicalState, Extraction, Fact
from app.llm.client import ProviderError
from app.llm.gemini_provider import (
    GeminiExtractionPayload,
    GeminiFactPayload,
    GeminiProvider,
)


def make_provider(response: object) -> tuple[GeminiProvider, Mock]:
    client = Mock()
    client.models.generate_content.return_value = response
    return GeminiProvider("test-key", "test-model", client=client), client


def test_gemini_adapter_uses_structured_output_without_patient_identity() -> None:
    extraction = Extraction(
        facts=[
            Fact(
                field="chief_complaint",
                value="fever",
                status="reported",
                evidence="fever",
            )
        ]
    )
    wire_extraction = GeminiExtractionPayload(
        facts=[
            GeminiFactPayload(
                field="chief_complaint",
                status="reported",
                text_value="fever",
                evidence="fever",
            )
        ]
    )
    provider, client = make_provider(SimpleNamespace(parsed=wire_extraction, text=None))

    result = provider.extract(
        "I have fever",
        QuestionGraph.question(OPENING, "en"),
        ClinicalState(),
    )

    assert result == extraction
    request = client.models.generate_content.call_args.kwargs
    payload = json.loads(request["contents"])
    assert request["model"] == "test-model"
    assert payload["statement"] == "I have fever"
    assert "patient_id" not in request["contents"]
    assert request["config"].response_schema is GeminiExtractionPayload
    assert request["config"].response_mime_type == "application/json"
    assert request["config"].system_instruction


def test_gemini_adapter_accepts_valid_json_text_fallback() -> None:
    extraction = Extraction(
        facts=[
            Fact(
                field="duration",
                value="3 days",
                status="reported",
                evidence="3 days",
            )
        ]
    )
    wire_extraction = GeminiExtractionPayload(
        facts=[
            GeminiFactPayload(
                field="duration",
                status="reported",
                text_value="3 days",
                evidence="3 days",
            )
        ]
    )
    provider, _ = make_provider(
        SimpleNamespace(parsed=None, text=wire_extraction.model_dump_json())
    )

    result = provider.extract(
        "For three days",
        QuestionGraph.question(OPENING, "en"),
        ClinicalState(),
    )

    assert result == extraction


def test_gemini_adapter_rejects_empty_response() -> None:
    provider, _ = make_provider(SimpleNamespace(parsed=None, text=None))

    with pytest.raises(ProviderError) as error:
        provider.extract(
            "I have fever",
            QuestionGraph.question(OPENING, "en"),
            ClinicalState(),
        )

    assert error.value.code == "incomplete_response"


def test_gemini_adapter_rejects_invalid_structured_output() -> None:
    provider, _ = make_provider(SimpleNamespace(parsed=None, text="not json"))

    with pytest.raises(ProviderError) as error:
        provider.extract(
            "I have fever",
            QuestionGraph.question(OPENING, "en"),
            ClinicalState(),
        )

    assert error.value.code == "invalid_provider_output"


def test_gemini_adapter_requires_credentials() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        GeminiProvider("")
