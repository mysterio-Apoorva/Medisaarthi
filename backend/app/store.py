"""Local-first relational persistence for MediKiosk.

The application deliberately starts on SQLite so a live demo does not depend on
cloud credentials.  The schema is normalized around patient facts, answers,
consents, documents, reconciliation, and audit records; SQLite can be replaced
behind this repository boundary without changing clinical code.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4
from backend.app import settings  # Load before resolving paths.


def now() -> str:
    return datetime.now(UTC).isoformat()


def _database_path() -> Path:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured.startswith("sqlite:///"):
        return Path(configured.removeprefix("sqlite:///"))
    return Path(os.getenv("MEDIKIOSK_DB_PATH", "backend/data/medikiosk.sqlite3"))


class Store:
    """Small repository over SQLite with one short-lived connection per action."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or _database_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connection() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('PATIENT','DOCTOR','ADMIN')),
                    patient_id TEXT REFERENCES patients(patient_id),
                    display_name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS patients (
                    patient_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    age INTEGER NOT NULL CHECK(age BETWEEN 0 AND 130),
                    gender TEXT NOT NULL,
                    language TEXT NOT NULL CHECK(language IN ('en','hi')),
                    uhid TEXT,
                    phone TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clinician_assignments (
                    doctor_user_id TEXT NOT NULL REFERENCES users(user_id),
                    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (doctor_user_id, patient_id)
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(user_id),
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS encounters (
                    encounter_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
                    status TEXT NOT NULL CHECK(status IN ('ACTIVE','PATIENT_REVIEW','SUBMITTED','FINALIZED')),
                    language TEXT NOT NULL CHECK(language IN ('en','hi')),
                    stage TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    ai_provider TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    finalized_at TEXT
                );
                CREATE TABLE IF NOT EXISTS answers (
                    answer_id TEXT PRIMARY KEY,
                    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id) ON DELETE CASCADE,
                    question_id TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    answer_text TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS clinical_facts (
                    fact_id TEXT PRIMARY KEY,
                    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id) ON DELETE CASCADE,
                    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
                    field_name TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    source TEXT NOT NULL CHECK(source IN ('PATIENT_REPORTED','DOCTOR_ENTERED','DOCUMENT_EXTRACTED','EXTERNAL_RECORD','AI_EXTRACTION','AI_INFERENCE')),
                    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                    status TEXT NOT NULL CHECK(status IN ('REPORTED','UNKNOWN','DECLINED','VERIFIED','REJECTED')),
                    evidence TEXT,
                    created_at TEXT NOT NULL,
                    superseded_at TEXT
                );
                CREATE INDEX IF NOT EXISTS ix_facts_encounter_field ON clinical_facts(encounter_id, field_name, created_at);
                CREATE TABLE IF NOT EXISTS red_flags (
                    flag_id TEXT PRIMARY KEY,
                    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id) ON DELETE CASCADE,
                    rule_code TEXT NOT NULL,
                    severity TEXT NOT NULL CHECK(severity IN ('INFO','MODERATE','HIGH','EMERGENCY')),
                    message TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolved_by TEXT REFERENCES users(user_id)
                );
                CREATE TABLE IF NOT EXISTS consents (
                    consent_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
                    encounter_id TEXT REFERENCES encounters(encounter_id),
                    consent_type TEXT NOT NULL,
                    version TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('GRANTED','WITHDRAWN')),
                    recorded_by TEXT REFERENCES users(user_id),
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
                    encounter_id TEXT REFERENCES encounters(encounter_id),
                    original_name TEXT NOT NULL,
                    stored_name TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    classification TEXT,
                    processing_status TEXT NOT NULL CHECK(processing_status IN ('PROCESSED','NEEDS_REVIEW','FAILED')),
                    error_code TEXT,
                    uploaded_by TEXT REFERENCES users(user_id),
                    uploaded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS document_extractions (
                    extraction_id TEXT PRIMARY KEY,
                    document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                    raw_text TEXT,
                    extracted_json TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                    provenance TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reconciliation_items (
                    reconciliation_id TEXT PRIMARY KEY,
                    encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id) ON DELETE CASCADE,
                    field_name TEXT NOT NULL,
                    current_fact_id TEXT REFERENCES clinical_facts(fact_id),
                    incoming_value_json TEXT NOT NULL,
                    incoming_source TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                    status TEXT NOT NULL CHECK(status IN ('OPEN','APPROVED','REJECTED','MERGED')),
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    resolved_by TEXT REFERENCES users(user_id)
                );
                CREATE TABLE IF NOT EXISTS timeline_events (
                    event_id TEXT PRIMARY KEY,
                    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
                    encounter_id TEXT REFERENCES encounters(encounter_id),
                    event_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_logs (
                    audit_id TEXT PRIMARY KEY,
                    actor_user_id TEXT REFERENCES users(user_id),
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS ontology_rules (
                    rule_id TEXT PRIMARY KEY,
                    concept TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                """
            )
            self._seed_demo(db)
            from backend.app.migrations import migrate
            migrate(db)

    @staticmethod
    def hash_password(password: str, salt: str | None = None) -> str:
        salt = salt or secrets.token_hex(16)
        derived = hashlib.scrypt(password.encode("utf-8"), salt=salt.encode("ascii"), n=2**14, r=8, p=1)
        return f"scrypt${salt}${derived.hex()}"

    @staticmethod
    def check_password(password: str, encoded: str) -> bool:
        try:
            _, salt, expected = encoded.split("$", 2)
            actual = Store.hash_password(password, salt).split("$", 2)[2]
            return secrets.compare_digest(actual, expected)
        except ValueError:
            return False

    def _seed_demo(self, db: sqlite3.Connection) -> None:
        """Seed only once. These are ordinary persisted records, never route fallbacks."""
        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return
        created = now()
        demo_patients = [
            ("P1001", "Rajesh Kumar (Synthetic)", 48, "Male", "hi", "SYN-APX-1001"),
            ("P1002", "Anita Sharma (Synthetic)", 36, "Female", "hi", "SYN-APX-1002"),
            ("P1003", "Rahul Singh (Synthetic)", 52, "Male", "en", "SYN-APX-1003"),
        ]
        db.executemany(
            "INSERT INTO patients(patient_id,name,age,gender,language,uhid,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
            [(pid, name, age, gender, language, uhid, created, created) for pid, name, age, gender, language, uhid in demo_patients],
        )
        demo_password = self.hash_password(os.getenv("DEMO_PASSWORD", "DemoPass!2026"))
        doctor_id, admin_id = "USR_DOCTOR_DEMO", "USR_ADMIN_DEMO"
        users = [
            (doctor_id, "doctor.demo@medikiosk.local", demo_password, "DOCTOR", None, "Dr. Asha Sharma"),
            (admin_id, "admin.demo@medikiosk.local", demo_password, "ADMIN", None, "MediKiosk Administrator"),
            ("USR_PATIENT_1001", "patient.demo@medikiosk.local", demo_password, "PATIENT", "P1001", "Rajesh Kumar (Synthetic)"),
        ]
        db.executemany(
            "INSERT INTO users(user_id,email,password_hash,role,patient_id,display_name,created_at) VALUES(?,?,?,?,?,?,?)",
            [(*row, created) for row in users],
        )
        db.executemany(
            "INSERT INTO clinician_assignments(doctor_user_id,patient_id,created_at) VALUES(?,?,?)",
            [(doctor_id, pid, created) for pid, *_ in demo_patients],
        )
        # One persisted, explicitly synthetic demonstration encounter.  It exercises the
        # real summary, flag, timeline, and doctor-verification paths without pretending
        # that it came from a live patient.
        encounter_id = "ENC_SYNTHETIC_CHEST_1001"
        db.execute(
            "INSERT INTO encounters(encounter_id,patient_id,status,language,stage,revision,ai_provider,started_at,completed_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (encounter_id, "P1001", "SUBMITTED", "en", "RECONCILIATION", 9, "clinical_rules", created, created),
        )
        seeded_facts = {
            "chief_complaint": "chest pain", "duration": "since yesterday", "severity": 8,
            "location": "central chest", "character": "pressure", "breathlessness": True,
            "sweating": True, "nausea": False, "past_medical_history": ["hypertension"],
            "medications": ["amlodipine 5 mg"], "allergies": [],
        }
        for field_name, value in seeded_facts.items():
            db.execute(
                "INSERT INTO clinical_facts(fact_id,encounter_id,patient_id,field_name,value_json,source,confidence,status,evidence,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (f"FAC_SEED_{field_name}", encounter_id, "P1001", field_name, json.dumps(value), "PATIENT_REPORTED", 1.0, "REPORTED", "Synthetic demo intake seed", created),
            )
        db.execute(
            "INSERT INTO red_flags(flag_id,encounter_id,rule_code,severity,message,evidence_json,created_at) VALUES(?,?,?,?,?,?,?)",
            ("FLG_SEED_CHEST", encounter_id, "CHEST_PAIN_BREATHLESSNESS", "EMERGENCY", "Chest discomfort with breathing difficulty needs immediate clinician assessment.", json.dumps(["chief_complaint", "breathlessness"]), created),
        )
        for pid, name, *_ in demo_patients:
            db.execute(
                "INSERT INTO timeline_events(event_id,patient_id,event_type,title,detail,source,confidence,occurred_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (f"EVT_SEED_{pid}", pid, "DEMO_PROFILE", "Synthetic demonstration profile created", f"{name} is explicitly synthetic seed data.", "SYSTEM_SEED", 1.0, created, created),
            )

    def audit(self, db: sqlite3.Connection, actor: str | None, action: str, resource_type: str, resource_id: str, metadata: dict[str, Any] | None = None) -> None:
        db.execute(
            "INSERT INTO audit_logs(audit_id,actor_user_id,action,resource_type,resource_id,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)",
            (f"AUD_{uuid4().hex}", actor, action, resource_type, resource_id, json.dumps(metadata or {}, ensure_ascii=False), now()),
        )

    @staticmethod
    def rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        return [dict(row) for row in rows]


store = Store()
