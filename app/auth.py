"""Small database-backed doctor authentication service for the Round 1 dashboard."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from app.persistence import SQLiteRepository, utcnow_iso


class AuthenticationError(ValueError):
    pass


class SetupUnavailable(ValueError):
    pass


class DoctorAuth:
    def __init__(self, repository: SQLiteRepository, session_hours: int = 12):
        self.repository = repository
        self.session_hours = session_hours

    @staticmethod
    def _derive(password: str, salt: bytes) -> str:
        return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000).hex()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def needs_setup(self) -> bool:
        with self.repository.connection() as connection:
            return connection.execute("SELECT 1 FROM doctors LIMIT 1").fetchone() is None

    def setup(self, username: str, display_name: str, password: str) -> dict[str, Any]:
        salt = secrets.token_bytes(32)
        with self.repository.connection() as connection:
            if connection.execute("SELECT 1 FROM doctors LIMIT 1").fetchone() is not None:
                raise SetupUnavailable("Initial doctor account already exists")
            cursor = connection.execute(
                """INSERT INTO doctors (username, display_name, password_hash, salt, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (username, display_name, self._derive(password, salt), salt.hex(), utcnow_iso()),
            )
            doctor_id = cursor.lastrowid
        return self._create_session(int(doctor_id), username, display_name)

    def login(self, username: str, password: str) -> dict[str, Any]:
        with self.repository.connection() as connection:
            row = connection.execute(
                "SELECT doctor_id, username, display_name, password_hash, salt FROM doctors WHERE username = ?",
                (username,),
            ).fetchone()
        if row is None:
            raise AuthenticationError("Invalid username or password")
        candidate = self._derive(password, bytes.fromhex(row["salt"]))
        if not hmac.compare_digest(candidate, row["password_hash"]):
            raise AuthenticationError("Invalid username or password")
        return self._create_session(row["doctor_id"], row["username"], row["display_name"])

    def _create_session(self, doctor_id: int, username: str, display_name: str) -> dict[str, Any]:
        token = secrets.token_urlsafe(40)
        now = datetime.now(UTC)
        expires = now + timedelta(hours=self.session_hours)
        with self.repository.connection() as connection:
            connection.execute(
                "DELETE FROM doctor_sessions WHERE expires_at <= ?", (now.isoformat(),)
            )
            connection.execute(
                """INSERT INTO doctor_sessions (token_hash, doctor_id, expires_at, created_at)
                   VALUES (?, ?, ?, ?)""",
                (self._token_hash(token), doctor_id, expires.isoformat(), now.isoformat()),
            )
        return {
            "access_token": token,
            "expires_at": expires,
            "doctor": {"doctor_id": doctor_id, "username": username, "display_name": display_name},
        }

    def authenticate(self, token: str) -> dict[str, Any]:
        with self.repository.connection() as connection:
            row = connection.execute(
                """SELECT d.doctor_id, d.username, d.display_name, s.expires_at
                   FROM doctor_sessions s JOIN doctors d ON d.doctor_id = s.doctor_id
                   WHERE s.token_hash = ?""",
                (self._token_hash(token),),
            ).fetchone()
        if row is None or datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
            raise AuthenticationError("Session is invalid or expired")
        return dict(row)
