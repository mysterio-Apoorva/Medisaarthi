"""Version 1 wire contracts. Null means unknown, never a negative finding."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")]
Language = Literal["en", "hi"]
ClinicalField = Literal[
    "chief_complaint",
    "hpi",
    "duration",
    "severity",
    "location",
    "temperature",
    "breathlessness",
    "breathlessness_onset",
    "cough",
    "sudden_onset",
    "vomiting",
    "past_medical_history",
    "medications",
    "allergies",
    "family_history",
    "personal_history",
]


def utcnow() -> datetime:
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Patient(Model):
    patient_id: Identifier
    name: str | None = None
    age: Annotated[int, Field(strict=True, ge=0, le=130)] | None = None
    gender: Literal["male", "female", "other", "unknown"] = "unknown"
    language: Language = "en"


class ClinicalState(Model):
    chief_complaint: str | None = None
    hpi: str | None = None
    duration: str | None = None
    severity: Annotated[int, Field(strict=True, ge=0, le=10)] | None = None
    location: str | None = None
    temperature: str | None = None
    breathlessness: Annotated[bool, Field(strict=True)] | None = None
    breathlessness_onset: str | None = None
    cough: Annotated[bool, Field(strict=True)] | None = None
    sudden_onset: Annotated[bool, Field(strict=True)] | None = None
    vomiting: Annotated[bool, Field(strict=True)] | None = None
    past_medical_history: list[str] | None = None
    medications: list[str] | None = None
    allergies: list[str] | None = None
    family_history: list[str] | None = None
    personal_history: list[str] | None = None


class Fact(Model):
    field: ClinicalField
    value: str | int | bool | list[str] | None
    status: Literal["reported", "unknown", "declined"]
    evidence: Annotated[str, Field(min_length=1, max_length=4000)]

    @model_validator(mode="after")
    def validate_value(self) -> "Fact":
        if (self.status == "reported") != (self.value is not None):
            raise ValueError("Reported facts need a value; unknown/declined facts must be null")
        ClinicalState.model_validate({self.field: self.value})
        if isinstance(self.value, str) and not self.value.strip():
            raise ValueError("Empty clinical values are not facts")
        if isinstance(self.value, list) and any(not item.strip() for item in self.value):
            raise ValueError("Empty list entries are not facts")
        return self


class Extraction(Model):
    facts: list[Fact] = Field(default_factory=list, max_length=30)
    uncertain_fields: list[ClinicalField] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_fields(self) -> "Extraction":
        fields = [fact.field for fact in self.facts]
        if len(fields) != len(set(fields)) or set(fields) & set(self.uncertain_fields):
            raise ValueError("Duplicate or simultaneously uncertain facts")
        return self


class NextQuestion(Model):
    id: ClinicalField
    text: str
    type: Literal["text"] = "text"
    language: Language
    clarification: bool = False


class Turn(Model):
    turn_id: int
    question: NextQuestion
    original_statement: str
    extraction: Extraction
    recorded_at: datetime = Field(default_factory=utcnow)


class PriorityFlag(Model):
    code: str
    message: str
    source: Literal["prototype_rule"] = "prototype_rule"
    evidence_fields: list[ClinicalField]


class Symptom(Model):
    name: str
    present: bool = True
    duration: str | None = None
    severity: int | None = None


class Interview(Model):
    schema_version: Literal["1.0"] = "1.0"
    interview_id: Identifier
    patient_id: Identifier
    language: Language
    consent: Literal[True]
    consent_recorded_at: datetime = Field(default_factory=utcnow)
    clinical_state: ClinicalState = Field(default_factory=ClinicalState)
    chief_complaint: str | None = None
    symptoms: list[Symptom] = Field(default_factory=list)
    responses: list[Turn] = Field(default_factory=list)
    completed: bool = False
    completion_reason: Literal["collected", "patient_requested", "turn_limit"] | None = None
    completed_at: datetime | None = None
    revision: int = 0


class InterviewResponse(Model):
    schema_version: Literal["1.0"] = "1.0"
    patient_id: Identifier
    interview_id: Identifier
    revision: int
    extracted: Extraction = Field(default_factory=Extraction)
    clinical_state: ClinicalState
    missing_information: list[ClinicalField]
    unknown_information: list[ClinicalField]
    next_question: NextQuestion | None
    priority_flags: list[PriorityFlag]
    completed: bool
    completion_reason: Literal["collected", "patient_requested", "turn_limit"] | None
