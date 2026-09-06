import os
from typing import Annotated, Literal

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field, StrictBool

from app.config import build_service
from app.interview.engine import InterviewConflict
from app.interview.schemas import Identifier, Interview, InterviewResponse, Model, Patient
from app.interview.state import InMemoryInterviewStore, InterviewNotFound, InterviewService
from app.llm.client import ProviderError
from app.llm.mock import MockProvider


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
    persistence: Literal["memory", "external"]


def create_app(service: InterviewService | None = None) -> FastAPI:
    service = service or build_service()
    app = FastAPI(
        title="MEDISAARTHI M2 — Interview Engine",
        version="1.0",
        description=(
            "Local demo API. Patient-reported information only; no diagnosis. "
            "Authentication and durable storage belong to M3."
        ),
    )

    cors_env = os.getenv(
        "M2_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    )
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

    @app.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(
            extraction_mode=(
                "mock" if isinstance(service.engine.provider, MockProvider) else "gemini"
            ),
            persistence=(
                "memory" if isinstance(service.store, InMemoryInterviewStore) else "external"
            ),
        )

    @app.exception_handler(InterviewNotFound)
    async def not_found(request: Request, exc: InterviewNotFound):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InterviewConflict)
    async def conflict(request: Request, exc: InterviewConflict):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ProviderError)
    async def provider_failure(request: Request, exc: ProviderError):
        request_id = exc.request_id
        return JSONResponse(
            status_code=502,
            content={
                "detail": str(exc),
                "code": exc.code,
                **({"provider_request_id": request_id} if request_id else {}),
            },
        )

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError):
        return JSONResponse(
            status_code=422, content={"detail": "Invalid interview input or consent missing"}
        )

    @app.post("/interview/start", response_model=InterviewResponse, status_code=201)
    def start(body: StartRequest):
        return service.start(body.patient, body.consent)

    @app.post("/interview/respond", response_model=InterviewResponse)
    def respond(body: RespondRequest):
        return service.respond(body.interview_id, body.response, body.expected_revision)

    @app.post("/interview/complete", response_model=InterviewResponse)
    def complete(body: CompleteRequest):
        return service.complete(body.interview_id, body.expected_revision)

    @app.get("/interview/{interview_id}", response_model=InterviewResponse)
    def get_state(interview_id: str):
        return service.get(interview_id)

    @app.get("/interview/{interview_id}/record", response_model=Interview)
    def get_record(interview_id: str):
        return service.store.get(interview_id)

    return app
