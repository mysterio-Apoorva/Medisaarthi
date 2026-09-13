"""Demo persistence boundary. M3 owns durable storage and access control."""

from threading import RLock
from typing import Protocol

from app.ai.interview.engine import InterviewConflict, InterviewEngine
from app.ai.interview.schemas import Interview, InterviewResponse, Patient


class InterviewNotFound(LookupError):
    pass


class InterviewStore(Protocol):
    def get(self, interview_id: str) -> Interview: ...
    def create(self, interview: Interview) -> None: ...
    def save(self, interview: Interview, expected_revision: int) -> None:
        """Atomically compare revision and write, or raise InterviewConflict."""
        ...


class InMemoryInterviewStore:
    """Process-local demo store: no persistence, no multi-worker consistency."""

    def __init__(self):
        self._records: dict[str, Interview] = {}
        self._lock = RLock()

    def get(self, interview_id: str) -> Interview:
        with self._lock:
            if interview_id not in self._records:
                raise InterviewNotFound("Interview not found")
            return self._records[interview_id].model_copy(deep=True)

    def create(self, interview: Interview) -> None:
        with self._lock:
            if interview.interview_id in self._records:
                raise InterviewConflict("Interview already exists")
            self._records[interview.interview_id] = interview.model_copy(deep=True)

    def save(self, interview: Interview, expected_revision: int) -> None:
        with self._lock:
            current = self.get(interview.interview_id)
            if current.revision != expected_revision:
                raise InterviewConflict("Stale revision; fetch state before retrying")
            self._records[interview.interview_id] = interview.model_copy(deep=True)


class InterviewService:
    def __init__(self, engine: InterviewEngine, store: InterviewStore):
        self.engine = engine
        self.store = store

    def start(self, patient: Patient, consent: bool) -> InterviewResponse:
        interview = self.engine.start(patient, consent)
        self.store.create(interview)
        return self.engine.present(interview)

    def get(self, interview_id: str) -> InterviewResponse:
        return self.engine.present(self.store.get(interview_id))

    def _current(self, interview_id: str, expected_revision: int) -> Interview:
        interview = self.store.get(interview_id)
        if interview.revision != expected_revision:
            raise InterviewConflict("Stale revision; fetch state before retrying")
        return interview

    def respond(
        self, interview_id: str, statement: str, expected_revision: int
    ) -> InterviewResponse:
        current = self._current(interview_id, expected_revision)
        updated = self.engine.respond(current, statement)
        self.store.save(updated, expected_revision)
        return self.engine.present(updated)

    def complete(self, interview_id: str, expected_revision: int) -> InterviewResponse:
        current = self._current(interview_id, expected_revision)
        updated = self.engine.complete(current)
        self.store.save(updated, expected_revision)
        return self.engine.present(updated)
