"""Durable SQL persistence for patients, interviews, history, summaries, and auth.

SQLite is used for the self-contained MVP.  The repository boundary keeps database
details out of the interview engine so a PostgreSQL adapter can replace it later.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from app.interview.engine import InterviewConflict
from app.interview.schemas import Interview, Patient
from app.interview.state import InterviewNotFound


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age BETWEEN 0 AND 130),
    gender TEXT NOT NULL CHECK (gender IN ('male','female','other','unknown')),
    language TEXT NOT NULL CHECK (language IN ('en','hi')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interviews (
    interview_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    record_json TEXT NOT NULL,
    revision INTEGER NOT NULL,
    completed INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interviews_patient ON interviews(patient_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS medical_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    condition TEXT NOT NULL,
    diagnosed_year TEXT,
    notes TEXT,
    source TEXT NOT NULL DEFAULT 'patient_record',
    source_date TEXT,
    confidence REAL NOT NULL DEFAULT 1.0 CHECK (confidence BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS medications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    dosage TEXT,
    frequency TEXT,
    notes TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS allergies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id) ON DELETE CASCADE,
    allergen TEXT NOT NULL,
    reaction TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS clinical_summaries (
    interview_id TEXT PRIMARY KEY REFERENCES interviews(interview_id) ON DELETE CASCADE,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    summary_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft','approved')),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    approved_at TEXT,
    approved_by INTEGER
);

CREATE TABLE IF NOT EXISTS doctors (
    doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS doctor_sessions (
    token_hash TEXT PRIMARY KEY,
    doctor_id INTEGER NOT NULL REFERENCES doctors(doctor_id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class PatientNotFound(LookupError):
    pass


class SummaryNotFound(LookupError):
    pass


class SQLiteRepository:
    """Thread-safe repository and InterviewStore implementation."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self.connection() as connection:
            connection.executescript(SCHEMA)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    # InterviewStore -----------------------------------------------------
    def get(self, interview_id: str) -> Interview:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT record_json FROM interviews WHERE interview_id = ?", (interview_id,)
            ).fetchone()
        if row is None:
            raise InterviewNotFound("Interview not found")
        return Interview.model_validate_json(row["record_json"])

    def create(self, interview: Interview) -> None:
        now = utcnow_iso()
        try:
            with self.connection() as connection:
                connection.execute(
                    """INSERT INTO interviews
                       (interview_id, patient_id, record_json, revision, completed, started_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        interview.interview_id,
                        interview.patient_id,
                        interview.model_dump_json(),
                        interview.revision,
                        int(interview.completed),
                        now,
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise InterviewConflict("Interview already exists or patient is missing") from exc

    def save(self, interview: Interview, expected_revision: int) -> None:
        now = utcnow_iso()
        with self._lock, self.connection() as connection:
            cursor = connection.execute(
                """UPDATE interviews
                   SET record_json = ?, revision = ?, completed = ?, updated_at = ?
                   WHERE interview_id = ? AND revision = ?""",
                (
                    interview.model_dump_json(),
                    interview.revision,
                    int(interview.completed),
                    now,
                    interview.interview_id,
                    expected_revision,
                ),
            )
            if cursor.rowcount != 1:
                raise InterviewConflict("Stale revision; fetch state before retrying")

    # Patients and history ----------------------------------------------
    def upsert_patient(self, patient: Patient) -> dict[str, Any]:
        if patient.name is None or patient.age is None:
            raise ValueError("Patient name and age are required")
        now = utcnow_iso()
        with self.connection() as connection:
            connection.execute(
                """INSERT INTO patients
                   (patient_id, name, age, gender, language, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(patient_id) DO UPDATE SET
                     name=excluded.name, age=excluded.age, gender=excluded.gender,
                     language=excluded.language, updated_at=excluded.updated_at""",
                (
                    patient.patient_id,
                    patient.name,
                    patient.age,
                    patient.gender,
                    patient.language,
                    now,
                    now,
                ),
            )
        return self.get_patient(patient.patient_id)

    def create_patient(self, patient: Patient) -> dict[str, Any]:
        return self.upsert_patient(patient)

    def get_patient(self, patient_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT patient_id, name, age, gender, language FROM patients WHERE patient_id = ?",
                (patient_id,),
            ).fetchone()
        if row is None:
            raise PatientNotFound("Patient not found")
        return dict(row)

    def list_patients(self) -> list[dict[str, Any]]:
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT p.patient_id, p.name, p.age, p.gender, p.language,
                          i.interview_id, i.completed, i.updated_at
                   FROM patients p
                   LEFT JOIN interviews i ON i.interview_id = (
                     SELECT i2.interview_id FROM interviews i2
                     WHERE i2.patient_id = p.patient_id ORDER BY i2.updated_at DESC LIMIT 1
                   )
                   ORDER BY COALESCE(i.updated_at, p.updated_at) DESC"""
            ).fetchall()
        return [dict(row) for row in rows]

    def get_history(self, patient_id: str) -> dict[str, Any]:
        self.get_patient(patient_id)
        with self.connection() as connection:
            conditions = [
                dict(row)
                for row in connection.execute(
                    """SELECT condition AS name, diagnosed_year AS since, notes, source,
                              source_date, confidence FROM medical_history
                       WHERE patient_id = ? ORDER BY COALESCE(source_date, diagnosed_year), id""",
                    (patient_id,),
                ).fetchall()
            ]
            medications = [
                dict(row)
                for row in connection.execute(
                    """SELECT name, dosage, frequency, notes, active FROM medications
                       WHERE patient_id = ? ORDER BY id""",
                    (patient_id,),
                ).fetchall()
            ]
            allergies = [
                dict(row)
                for row in connection.execute(
                    "SELECT allergen AS name, reaction, notes FROM allergies WHERE patient_id = ? ORDER BY id",
                    (patient_id,),
                ).fetchall()
            ]
        for medication in medications:
            medication["active"] = bool(medication["active"])
        return {
            "patient_id": patient_id,
            "conditions": conditions,
            "medications": medications,
            "allergies": allergies,
        }

    def replace_history(self, patient_id: str, history: dict[str, Any]) -> dict[str, Any]:
        self.get_patient(patient_id)
        with self._lock, self.connection() as connection:
            for table in ("medical_history", "medications", "allergies"):
                connection.execute(f"DELETE FROM {table} WHERE patient_id = ?", (patient_id,))
            connection.executemany(
                """INSERT INTO medical_history
                   (patient_id, condition, diagnosed_year, notes, source, source_date, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        patient_id,
                        item["name"],
                        item.get("since"),
                        item.get("notes"),
                        item.get("source", "patient_record"),
                        item.get("source_date"),
                        item.get("confidence", 1.0),
                    )
                    for item in history.get("conditions", [])
                ],
            )
            connection.executemany(
                """INSERT INTO medications
                   (patient_id, name, dosage, frequency, notes, active) VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        patient_id,
                        item["name"],
                        item.get("dosage"),
                        item.get("frequency"),
                        item.get("notes"),
                        int(item.get("active", True)),
                    )
                    for item in history.get("medications", [])
                ],
            )
            connection.executemany(
                "INSERT INTO allergies (patient_id, allergen, reaction, notes) VALUES (?, ?, ?, ?)",
                [
                    (patient_id, item["name"], item.get("reaction"), item.get("notes"))
                    for item in history.get("allergies", [])
                ],
            )
        return self.get_history(patient_id)

    # Summaries ----------------------------------------------------------
    def save_summary(
        self, interview_id: str, patient_id: str, summary: dict[str, Any]
    ) -> dict[str, Any]:
        now = utcnow_iso()
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT version, status, created_at FROM clinical_summaries WHERE interview_id = ?",
                (interview_id,),
            ).fetchone()
            version = int(existing["version"]) if existing else 1
            status = existing["status"] if existing else "draft"
            created_at = existing["created_at"] if existing else now
            connection.execute(
                """INSERT OR REPLACE INTO clinical_summaries
                   (interview_id, patient_id, summary_json, status, version, created_at, updated_at,
                    approved_at, approved_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)""",
                (interview_id, patient_id, json.dumps(summary), status, version, created_at, now),
            )
        return self.get_summary(interview_id)

    def get_summary(self, interview_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM clinical_summaries WHERE interview_id = ?", (interview_id,)
            ).fetchone()
        if row is None:
            raise SummaryNotFound("Clinical summary not found")
        result = json.loads(row["summary_json"])
        result.update(
            status=row["status"],
            version=row["version"],
            updated_at=row["updated_at"],
            approved_at=row["approved_at"],
        )
        return result

    def latest_interview_id(self, patient_id: str, completed_only: bool = True) -> str:
        self.get_patient(patient_id)
        condition = "AND completed = 1" if completed_only else ""
        with self.connection() as connection:
            row = connection.execute(
                f"""SELECT interview_id FROM interviews WHERE patient_id = ? {condition}
                    ORDER BY updated_at DESC LIMIT 1""",
                (patient_id,),
            ).fetchone()
        if row is None:
            raise InterviewNotFound("No completed interview found for patient")
        return str(row["interview_id"])

    def update_summary(
        self, interview_id: str, summary: dict[str, Any], expected_version: int
    ) -> dict[str, Any]:
        now = utcnow_iso()
        with self._lock, self.connection() as connection:
            cursor = connection.execute(
                """UPDATE clinical_summaries SET summary_json = ?, status = 'draft',
                     version = version + 1, updated_at = ?, approved_at = NULL, approved_by = NULL
                   WHERE interview_id = ? AND version = ?""",
                (json.dumps(summary), now, interview_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise InterviewConflict("Summary changed; reload before saving")
        return self.get_summary(interview_id)

    def approve_summary(
        self, interview_id: str, doctor_id: int, expected_version: int
    ) -> dict[str, Any]:
        now = utcnow_iso()
        with self._lock, self.connection() as connection:
            cursor = connection.execute(
                """UPDATE clinical_summaries SET status = 'approved', version = version + 1,
                     updated_at = ?, approved_at = ?, approved_by = ?
                   WHERE interview_id = ? AND version = ?""",
                (now, now, doctor_id, interview_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise InterviewConflict("Summary changed; reload before approving")
        return self.get_summary(interview_id)

    def timeline(self, patient_id: str) -> list[dict[str, Any]]:
        history = self.get_history(patient_id)
        events: list[dict[str, Any]] = []
        for item in history["conditions"]:
            events.append(
                {
                    "date": item.get("source_date") or item.get("since"),
                    "title": item["name"],
                    "detail": item.get("notes"),
                    "source": item.get("source") or "patient_record",
                    "confidence": item.get("confidence", 1.0),
                }
            )
        with self.connection() as connection:
            rows = connection.execute(
                """SELECT record_json, updated_at FROM interviews
                   WHERE patient_id = ? AND completed = 1 ORDER BY updated_at""",
                (patient_id,),
            ).fetchall()
        for row in rows:
            record = Interview.model_validate_json(row["record_json"])
            events.append(
                {
                    "date": record.completed_at.isoformat()
                    if record.completed_at
                    else row["updated_at"],
                    "title": record.chief_complaint or "Pre-consultation interview",
                    "detail": f"Interview {record.interview_id}",
                    "source": "patient_interview",
                    "confidence": 1.0,
                }
            )
        return sorted(events, key=lambda item: item["date"] or "")
