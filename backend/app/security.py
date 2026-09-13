"""Authentication, resource authorization, and safe HTTP dependencies."""

from __future__ import annotations

import hashlib
import os
import secrets
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from backend.app.store import Store, now, store

Role = Literal["PATIENT", "DOCTOR", "ADMIN"]


class AuthenticatedUser(BaseModel):
    user_id: str
    email: str
    role: Role
    patient_id: str | None = None
    display_name: str


class LoginInput(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("A valid email address is required")
        return value.casefold().strip()


class PatientRegistration(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    age: int = Field(ge=0, le=130)
    gender: Literal["Male", "Female", "Other"]
    language: Literal["en", "hi"] = "en"
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=256)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        if "@" not in value or value.startswith("@") or value.endswith("@"):
            raise ValueError("A valid email address is required")
        return value.casefold().strip()


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_session(user_id: str) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.now(UTC) + timedelta(hours=8)).isoformat()
    with store.connection() as db:
        db.execute("DELETE FROM sessions WHERE expires_at < ?", (now(),))
        db.execute(
            "INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token_digest(token), user_id, expires_at, now()),
        )
        store.audit(db, user_id, "LOGIN", "SESSION", user_id)
    return token, expires_at


def clear_session(token: str | None) -> None:
    if not token:
        return
    with store.connection() as db:
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (token_digest(token),))


def _token_from_request(request: Request, authorization: str | None) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return request.cookies.get("medikiosk_session")


def current_user(
    request: Request,
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    token = _token_from_request(request, authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required")
    with store.connection() as db:
        row = db.execute(
            """
            SELECT u.user_id,u.email,u.role,u.patient_id,u.display_name
            FROM sessions s JOIN users u ON u.user_id=s.user_id
            WHERE s.token_hash=? AND s.expires_at > ?
            """,
            (token_digest(token), now()),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session is invalid or expired")
    return AuthenticatedUser(**dict(row))


def require_roles(*roles: Role):
    def dependency(user: AuthenticatedUser = Depends(current_user)) -> AuthenticatedUser:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission for this action")
        return user
    return dependency


def assert_patient_access(db: sqlite3.Connection, user: AuthenticatedUser, patient_id: str) -> None:
    if user.role == "ADMIN":
        return
    if user.role == "PATIENT" and user.patient_id == patient_id:
        return
    if user.role == "DOCTOR":
        assignment = db.execute(
            "SELECT 1 FROM clinician_assignments WHERE doctor_user_id=? AND patient_id=?",
            (user.user_id, patient_id),
        ).fetchone()
        if assignment:
            return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not authorized to access this patient record")


def cookie_kwargs(expires_at: str) -> dict[str, object]:
    return {
        "httponly": True,
        "secure": os.getenv("COOKIE_SECURE", "false").lower() == "true",
        "samesite": "lax",
        "max_age": max(1, int((datetime.fromisoformat(expires_at) - datetime.now(UTC)).total_seconds())),
        "path": "/",
    }
