"""Explicit synthetic seed data. Never imported as a clinical result fallback."""
import json
import os
import sqlite3
from backend.app.store import now


def seed_demo(self, db: sqlite3.Connection) -> None:
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
