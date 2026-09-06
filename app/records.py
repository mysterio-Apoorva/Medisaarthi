"""API contracts for longitudinal records and physician review."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from app.interview.schemas import Identifier, Model, Patient


class Condition(Model):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    since: str | None = None
    notes: str | None = None
    source: str = "patient_record"
    source_date: str | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] = 1.0


class Medication(Model):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    dosage: str | None = None
    frequency: str | None = None
    notes: str | None = None
    active: bool = True


class Allergy(Model):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    reaction: str | None = None
    notes: str | None = None


class PatientHistory(Model):
    patient_id: Identifier
    conditions: list[Condition] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)


class HistoryUpdate(Model):
    conditions: list[Condition] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)
    allergies: list[Allergy] = Field(default_factory=list)


class CurrentComplaint(Model):
    name: str | None = None
    duration: str | None = None
    severity: Annotated[int, Field(ge=0, le=10)] | None = None


class PatientSnapshot(Model):
    patient_id: Identifier
    name: str
    age: int
    gender: str
    language: str


class EditableClinicalSummary(Model):
    patient_snapshot: PatientSnapshot
    current_complaint: CurrentComplaint
    interview_summary: Annotated[str, Field(max_length=5000)]
    past_history: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    important_findings: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    priority_flags: list[str] = Field(default_factory=list)


class ClinicalSummary(EditableClinicalSummary):
    interview_id: Identifier
    patient_id: Identifier
    status: Literal["draft", "approved"] = "draft"
    version: int = 1
    updated_at: datetime | None = None
    approved_at: datetime | None = None


class SummaryUpdate(Model):
    summary: EditableClinicalSummary
    expected_version: Annotated[int, Field(ge=1)]


class SummaryApprove(Model):
    expected_version: Annotated[int, Field(ge=1)]


class TimelineEvent(Model):
    date: str | None = None
    title: str
    detail: str | None = None
    source: str
    confidence: Annotated[float, Field(ge=0, le=1)]


class DoctorPatient(Model):
    patient: Patient
    interview_id: str | None = None
    completed: bool = False
    updated_at: datetime | None = None
    chief_complaint: str | None = None
    summary_status: Literal["draft", "approved"] | None = None


class AuthCredentials(Model):
    username: Annotated[str, Field(min_length=3, max_length=80, pattern=r"^[A-Za-z0-9_.-]+$")]
    password: Annotated[str, Field(min_length=8, max_length=200)]


class SetupRequest(AuthCredentials):
    display_name: Annotated[str, Field(min_length=2, max_length=120)]


class AuthToken(Model):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_at: datetime
    doctor: dict[str, str | int]


class AuthStatus(Model):
    needs_setup: bool
