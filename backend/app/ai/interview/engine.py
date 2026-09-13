"""Stateless orchestration: M3 can persist the returned Interview in any store."""

import logging
from uuid import uuid4

from pydantic import TypeAdapter, ValidationError

from app.ai.extraction import HISTORY_FIELDS, apply_extraction
from app.ai.interview.graph import QuestionGraph
from app.ai.interview.schemas import (
    ClinicalField,
    Extraction,
    Fact,
    Interview,
    InterviewResponse,
    Patient,
    Symptom,
    Turn,
    utcnow,
)
from app.ai.llm.client import LLMClient, ProviderError
from app.ai.safety import priority_flags

logger = logging.getLogger(__name__)


class InterviewConflict(ValueError):
    """Invalid transition, stale revision, or response to a closed interview."""


class InterviewEngine:
    def __init__(
        self, provider: LLMClient, graph: QuestionGraph | None = None, max_turns: int = 40
    ):
        if max_turns < 1:
            raise ValueError("max_turns must be positive")
        self.provider = provider
        self.graph = graph or QuestionGraph()
        self.max_turns = max_turns

    def start(self, patient: Patient, consent: bool) -> Interview:
        if consent is not True:
            raise ValueError("Explicit patient consent is required")
        return Interview(
            interview_id=f"INT_{uuid4().hex}",
            patient_id=patient.patient_id,
            language=patient.language,
            consent=True,
        )

    @staticmethod
    def latest_facts(interview: Interview) -> dict[ClinicalField, Fact]:
        latest: dict[ClinicalField, Fact] = {}
        for turn in interview.responses:
            complaint = next(
                (fact for fact in turn.extraction.facts if fact.field == "chief_complaint"), None
            )
            previous = latest.get("chief_complaint")
            if complaint is not None and previous is not None and complaint.value != previous.value:
                latest = {field: fact for field, fact in latest.items() if field in HISTORY_FIELDS}
            latest.update({fact.field: fact for fact in turn.extraction.facts})
        return latest

    def present(self, interview: Interview) -> InterviewResponse:
        latest = self.latest_facts(interview)
        answered = set(latest)
        if interview.clinical_state.chief_complaint is None:
            answered.discard("chief_complaint")
        missing = self.graph.missing(interview.clinical_state, answered)
        next_question = None
        if missing and not interview.completed:
            clarify = bool(
                interview.responses
                and missing[0].field == interview.responses[-1].question.id
                and missing[0].field
                not in {f.field for f in interview.responses[-1].extraction.facts}
            )
            if clarify and len(interview.responses) >= 2:
                prev_q = interview.responses[-2].question
                if getattr(prev_q, "clarification", False) and prev_q.id == missing[0].field:
                    clarify = False
            next_question = self.graph.question(missing[0], interview.language, clarify)
        return InterviewResponse(
            patient_id=interview.patient_id,
            interview_id=interview.interview_id,
            revision=interview.revision,
            extracted=interview.responses[-1].extraction if interview.responses else Extraction(),
            clinical_state=interview.clinical_state.model_copy(deep=True),
            missing_information=[node.field for node in missing],
            unknown_information=[
                field for field, fact in latest.items() if fact.status != "reported"
            ],
            next_question=next_question,
            priority_flags=priority_flags(interview.clinical_state),
            completed=interview.completed,
            completion_reason=interview.completion_reason,
        )

    def respond(self, interview: Interview, statement: str) -> Interview:
        statement = TypeAdapter(str).validate_python(statement).strip()
        if not statement or len(statement) > 4000:
            raise ValueError("Response must contain 1 to 4000 characters")
        if interview.completed:
            raise InterviewConflict("Interview is already complete")
        question = self.present(interview).next_question
        if question is None:
            raise InterviewConflict("Interview has no pending question")
        try:
            extraction = self.provider.extract(
                statement, question, interview.clinical_state.model_copy(deep=True)
            )
            extraction = Extraction.model_validate(extraction)
            state = apply_extraction(interview.clinical_state, extraction, statement)
        except ValidationError as exc:
            raise ProviderError("Provider returned invalid extraction") from exc
        except ProviderError as exc:
            logger.warning(
                "Interview extraction failed: code=%s detail=%s; state unchanged",
                exc.code,
                str(exc),
            )
            raise
        updated = interview.model_copy(deep=True)
        updated.clinical_state = state
        updated.chief_complaint = state.chief_complaint
        updated.symptoms = self._symptoms(updated)
        updated.responses.append(
            Turn(
                turn_id=len(updated.responses) + 1,
                question=question,
                original_statement=statement,
                extraction=extraction,
            )
        )
        updated.revision += 1
        if not self.present(updated).missing_information:
            self._close(updated, "collected")
        elif len(updated.responses) >= self.max_turns:
            self._close(updated, "turn_limit")
        return updated

    def complete(self, interview: Interview) -> Interview:
        if interview.completed:
            return interview.model_copy(deep=True)
        updated = interview.model_copy(deep=True)
        updated.revision += 1
        self._close(updated, "patient_requested")
        return updated

    @staticmethod
    def _close(interview: Interview, reason) -> None:
        interview.completed = True
        interview.completion_reason = reason
        interview.completed_at = utcnow()

    @staticmethod
    def _symptoms(interview: Interview) -> list[Symptom]:
        state = interview.clinical_state
        result = []
        if state.chief_complaint:
            result.append(
                Symptom(
                    name=state.chief_complaint, duration=state.duration, severity=state.severity
                )
            )
        for field in ("breathlessness", "cough", "vomiting"):
            present = getattr(state, field)
            if present is not None:
                result.append(Symptom(name=field, present=present))
        return result
