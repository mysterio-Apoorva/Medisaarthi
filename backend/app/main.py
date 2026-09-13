from __future__ import annotations

import logging
import os
import time
from collections import defaultdict, deque
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.routes.admin import router as admin_router
from backend.app.routes.auth import router as auth_router
from backend.app.routes.doctor import router as doctor_router
from backend.app.routes.documents import router as document_router
from backend.app.routes.interviews import router as interview_router
from backend.app.routes.patients import router as patient_router
from backend.app.store import store
from backend.app.tts import router as speech_router
from backend.app.routes.knowledge import router as knowledge_router
from backend.app.routes.followups import router as follow_up_router

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("medikiosk")


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.initialize()
    logger.info("medikiosk_started persistence=sqlite provider=%s", os.getenv("AI_PROVIDER", "ollama"))
    yield


app = FastAPI(
    title="MediKiosk Clinical Intake API",
    description="Persistent, clinician-supervised pre-consultation history taking. Not a diagnostic service.",
    version="2.0.0",
    lifespan=lifespan,
)

# Keep cookie-based sessions restricted to explicit local UI origins. Port 3001
# is the conventional second local Next.js instance used for a production-build
# or browser-test run while a developer keeps port 3000 open.
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "PUT", "PATCH", "OPTIONS"], allow_headers=["Authorization", "Content-Type"])

_request_windows = defaultdict(deque)


@app.middleware('http')
async def request_boundary(request: Request, call_next):
    request_id = uuid4().hex
    started = time.monotonic()
    if request.method in {'POST','PUT','PATCH','DELETE'}:
        origin = request.headers.get('origin')
        if origin and origin not in allowed_origins:
            return JSONResponse(status_code=403, content={'detail':'This request origin is not allowed'})
        length = request.headers.get('content-length', '0')
        if not length.isdigit() or int(length) > 16 * 1024 * 1024:
            return JSONResponse(status_code=413, content={'detail':'Request exceeds the upload limit'})
        if request.url.path.startswith(('/auth/login','/auth/register','/speech/')):
            key = (request.client.host if request.client else 'unknown', request.url.path.split('/')[1])
            window = _request_windows[key]
            current = time.monotonic()
            while window and current - window[0] > 60:
                window.popleft()
            if len(window) >= 60:
                return JSONResponse(status_code=429, content={'detail':'Too many requests. Please wait a minute.'}, headers={'Retry-After':'60'})
            window.append(current)
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store'
    logger.info('request_completed id=%s method=%s status=%s duration_ms=%d', request_id, request.method, response.status_code, int((time.monotonic()-started)*1000))
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError):
    # Keep validation useful without mirroring raw values or internal stack details.
    return JSONResponse(status_code=422, content={"detail": "Request validation failed", "errors": [{"field": ".".join(str(part) for part in error["loc"]), "message": error["msg"]} for error in exc.errors()]})


@app.exception_handler(Exception)
async def unexpected_error(_: Request, exc: Exception):
    logger.exception("unhandled_request_error type=%s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "The service could not complete this request. Please retry."})


app.include_router(auth_router)
app.include_router(patient_router)
app.include_router(interview_router)
app.include_router(document_router)
app.include_router(doctor_router)
app.include_router(admin_router)
app.include_router(speech_router)
app.include_router(knowledge_router)
app.include_router(follow_up_router)


@app.get("/")
def root():
    return {"service": "MediKiosk", "version": "2.0.0", "clinical_notice": "Pre-consultation support only; clinician review is required."}


@app.get("/health")
def health():
    try:
        with store.connection() as db:
            db.execute("SELECT 1").fetchone()
        return {"status": "ok", "persistence": "sqlite", "ai_provider": os.getenv("AI_PROVIDER", "ollama"), "ai_fallback": "clinical_rules"}
    except Exception:
        logger.exception("health_check_failed")
        return JSONResponse(status_code=503, content={"status": "unavailable"})
