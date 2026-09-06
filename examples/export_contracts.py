"""Generate checked-in contracts from the actual runtime models."""

import json
from pathlib import Path

from app.api.main import CompleteRequest, RespondRequest, StartRequest
from app.interview.schemas import ClinicalState, Interview, InterviewResponse, NextQuestion, Patient
from app.records import ClinicalSummary, PatientHistory, TimelineEvent

MODELS = {
    "patient": Patient,
    "interview": Interview,
    "interview_response": InterviewResponse,
    "clinical_state": ClinicalState,
    "next_question": NextQuestion,
    "start_request": StartRequest,
    "respond_request": RespondRequest,
    "complete_request": CompleteRequest,
    "history": PatientHistory,
    "clinical_summary": ClinicalSummary,
    "timeline": TimelineEvent,
}


def export() -> None:
    target = Path(__file__).resolve().parents[1] / "contracts"
    target.mkdir(exist_ok=True)
    for name, model in MODELS.items():
        schema = model.model_json_schema()
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        (target / f"{name}.schema.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    export()
