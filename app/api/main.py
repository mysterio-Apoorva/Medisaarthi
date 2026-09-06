import os
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool

from app.auth import AuthenticationError, DoctorAuth, SetupUnavailable
from app.clinical import build_clinical_summary
from app.config import build_service
from app.interview.engine import InterviewConflict
from app.interview.schemas import Identifier, Interview, InterviewResponse, Model, Patient
from app.interview.state import InMemoryInterviewStore, InterviewNotFound, InterviewService
from app.llm.client import ProviderError
from app.llm.mock import MockProvider
from app.persistence import PatientNotFound, SQLiteRepository, SummaryNotFound
from app.records import (
    AuthCredentials,
    AuthStatus,
    AuthToken,
    ClinicalSummary,
    DoctorPatient,
    HistoryUpdate,
    PatientHistory,
    SetupRequest,
    SummaryApprove,
    SummaryUpdate,
    TimelineEvent,
)


class StartRequest(Model):
    patient: Patient
    consent: StrictBool


class CompleteRequest(Model):
    interview_id: Identifier
    expected_revision: Annotated[int, Field(strict=True, ge=0)]


class RespondRequest(CompleteRequest):
    response: Annotated[str, Field(min_length=1, max_length=4000)]


class HealthResponse(Model):
    status: Literal["ok"] = "ok"
    schema_version: Literal["1.0"] = "1.0"
    extraction_mode: Literal["mock", "gemini"]
    persistence: Literal["memory", "sqlite"]


def _default_database_path() -> Path:
    configured = os.getenv("MEDISAARTHI_DB_PATH")
    return Path(configured) if configured else Path.cwd() / "data" / "medisaarthi.db"


def create_app(
    service: InterviewService | None = None,
    repository: SQLiteRepository | None = None,
) -> FastAPI:
    if service is None:
        repository = repository or SQLiteRepository(_default_database_path())
        service = build_service(store=repository)

    app = FastAPI(
        title="MEDISAARTHI — Pre-Consultation Intelligence",
        version="1.0",
        description=(
            "Adaptive patient interview, durable longitudinal history, and verified "
            "physician briefing. This system does not diagnose or prescribe."
        ),
    )

    cors_env = os.getenv("M2_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    allow_origins = [origin.strip() for origin in cors_env.split(",") if origin.strip()]
    if "*" in allow_origins:
        allow_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.interview_service = service
    app.state.repository = repository
    auth = DoctorAuth(repository) if repository is not None else None

    def require_repository() -> SQLiteRepository:
        if repository is None:
            raise RuntimeError("Longitudinal data API is not configured")
        return repository

    def current_doctor(authorization: str | None = Header(default=None)) -> dict:
        if auth is None:
            raise AuthenticationError("Doctor authentication is not configured")
        if not authorization or not authorization.lower().startswith("bearer "):
            raise AuthenticationError("A doctor session is required")
        return auth.authenticate(authorization.split(" ", 1)[1].strip())

    DoctorSession = Annotated[dict, Depends(current_doctor)]

    def ensure_summary(interview_id: str) -> dict:
        data = require_repository()
        try:
            return data.get_summary(interview_id)
        except SummaryNotFound:
            interview = data.get(interview_id)
            if not interview.completed:
                raise InterviewConflict("Interview must be completed before it can be summarized")
            summary = build_clinical_summary(
                data.get_patient(interview.patient_id),
                interview,
                data.get_history(interview.patient_id),
                service.engine,
            )
            return data.save_summary(interview_id, interview.patient_id, summary)

    @app.exception_handler(InterviewNotFound)
    @app.exception_handler(PatientNotFound)
    @app.exception_handler(SummaryNotFound)
    async def not_found(request: Request, exc: LookupError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InterviewConflict)
    @app.exception_handler(SetupUnavailable)
    async def conflict(request: Request, exc: ValueError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def unauthorized(request: Request, exc: AuthenticationError):
        return JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
            headers={"WWW-Authenticate": "Bearer"},
        )

    @app.exception_handler(ProviderError)
    async def provider_failure(request: Request, exc: ProviderError):
        return JSONResponse(
            status_code=502,
            content={
                "detail": str(exc),
                "code": exc.code,
                **({"provider_request_id": exc.request_id} if exc.request_id else {}),
            },
        )

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/")
    def root():
        return {"name": "MEDISAARTHI", "docs": "/docs", "health": "/health"}

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(
            extraction_mode=(
                "mock" if isinstance(service.engine.provider, MockProvider) else "gemini"
            ),
            persistence=(
                "memory" if isinstance(service.store, InMemoryInterviewStore) else "sqlite"
            ),
        )

    @app.post("/patients", response_model=Patient, status_code=201)
    def create_patient(patient: Patient):
        return require_repository().create_patient(patient)

    @app.get("/patients", response_model=list[Patient])
    def list_patients(doctor: DoctorSession):
        return [
            {key: item[key] for key in ("patient_id", "name", "age", "gender", "language")}
            for item in require_repository().list_patients()
        ]

    @app.get("/patients/{patient_id}", response_model=Patient)
    def get_patient(patient_id: str, doctor: DoctorSession):
        return require_repository().get_patient(patient_id)

    @app.get("/patients/{patient_id}/history", response_model=PatientHistory)
    def get_patient_history(patient_id: str, doctor: DoctorSession):
        return require_repository().get_history(patient_id)

    @app.put("/patients/{patient_id}/history", response_model=PatientHistory)
    def update_patient_history(patient_id: str, body: HistoryUpdate, doctor: DoctorSession):
        return require_repository().replace_history(patient_id, body.model_dump())

    @app.post("/interview/start", response_model=InterviewResponse, status_code=201)
    def start(body: StartRequest):
        if repository is not None:
            repository.upsert_patient(body.patient)
        return service.start(body.patient, body.consent)

    @app.post("/interview/respond", response_model=InterviewResponse)
    def respond(body: RespondRequest):
        result = service.respond(body.interview_id, body.response, body.expected_revision)
        if result.completed and repository is not None:
            ensure_summary(body.interview_id)
        return result

    @app.post("/interview/complete", response_model=InterviewResponse)
    def complete(body: CompleteRequest):
        result = service.complete(body.interview_id, body.expected_revision)
        if repository is not None:
            ensure_summary(body.interview_id)
        return result

    @app.get("/interview/{interview_id}", response_model=InterviewResponse)
    def get_state(interview_id: str):
        return service.get(interview_id)

    @app.get("/interview/{interview_id}/record", response_model=Interview)
    def get_record(
        interview_id: str,
        authorization: str | None = Header(default=None),
    ):
        if repository is not None:
            current_doctor(authorization)
        return service.store.get(interview_id)

    @app.get("/auth/status", response_model=AuthStatus)
    def auth_status():
        return AuthStatus(needs_setup=bool(auth and auth.needs_setup()))

    @app.post("/auth/setup", response_model=AuthToken, status_code=201)
    def setup_doctor(body: SetupRequest):
        if auth is None:
            raise SetupUnavailable("Doctor authentication is not configured")
        return auth.setup(body.username, body.display_name, body.password)

    @app.post("/auth/login", response_model=AuthToken)
    def login_doctor(body: AuthCredentials):
        if auth is None:
            raise AuthenticationError("Doctor authentication is not configured")
        return auth.login(body.username, body.password)

    @app.get("/doctor/patients", response_model=list[DoctorPatient])
    def doctor_patients(doctor: DoctorSession):
        data = require_repository()
        result = []
        for row in data.list_patients():
            complaint = None
            status = None
            if row.get("interview_id"):
                complaint = data.get(row["interview_id"]).chief_complaint
                try:
                    status = data.get_summary(row["interview_id"])["status"]
                except SummaryNotFound:
                    status = None
            result.append(
                {
                    "patient": {
                        key: row[key] for key in ("patient_id", "name", "age", "gender", "language")
                    },
                    "interview_id": row.get("interview_id"),
                    "completed": bool(row.get("completed")),
                    "updated_at": row.get("updated_at"),
                    "chief_complaint": complaint,
                    "summary_status": status,
                }
            )
        return result

    @app.get("/doctor/patients/{patient_id}/summary", response_model=ClinicalSummary)
    def doctor_summary(
        patient_id: str,
        doctor: DoctorSession,
        interview_id: str | None = Query(default=None),
    ):
        data = require_repository()
        selected = interview_id or data.latest_interview_id(patient_id)
        interview = data.get(selected)
        if interview.patient_id != patient_id:
            raise PatientNotFound("Interview does not belong to this patient")
        return ensure_summary(selected)

    @app.put("/doctor/interviews/{interview_id}/summary", response_model=ClinicalSummary)
    def edit_summary(
        interview_id: str,
        body: SummaryUpdate,
        doctor: DoctorSession,
    ):
        data = require_repository()
        interview = data.get(interview_id)
        stored = {
            "interview_id": interview_id,
            "patient_id": interview.patient_id,
            **body.summary.model_dump(),
        }
        return data.update_summary(interview_id, stored, body.expected_version)

    @app.post("/doctor/interviews/{interview_id}/approve", response_model=ClinicalSummary)
    def approve_summary(
        interview_id: str,
        body: SummaryApprove,
        doctor: DoctorSession,
    ):
        return require_repository().approve_summary(
            interview_id, int(doctor["doctor_id"]), body.expected_version
        )

    @app.get("/doctor/patients/{patient_id}/timeline", response_model=list[TimelineEvent])
    def patient_timeline(patient_id: str, doctor: DoctorSession):
        return require_repository().timeline(patient_id)

    return app
