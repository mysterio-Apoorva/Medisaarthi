from pydantic import BaseModel, Field


# -------------------------
# Patient
# -------------------------

class PatientCreate(BaseModel):
    patient_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    age: int = Field(ge=0, le=150)
    gender: str = Field(min_length=1)
    language: str = "en"


class PatientResponse(BaseModel):
    patient_id: str
    name: str
    age: int
    gender: str
    language: str


# -------------------------
# Interview
# -------------------------

class InterviewStart(BaseModel):
    patient_id: str = Field(min_length=1)


class InterviewResponseCreate(BaseModel):
    interview_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    question_number: int = Field(ge=1)


# -------------------------
# History
# -------------------------

class MedicalHistoryResponse(BaseModel):
    condition: str
    diagnosed_year: int | None = None
    notes: str | None = None


class MedicationResponse(BaseModel):
    name: str
    dosage: str | None = None
    frequency: str | None = None
    notes: str | None = None


class AllergyResponse(BaseModel):
    allergen: str
    reaction: str | None = None


class PatientHistoryResponse(BaseModel):
    patient: PatientResponse
    medical_history: list[MedicalHistoryResponse]
    medications: list[MedicationResponse]
    allergies: list[AllergyResponse]