"""Additive, versioned migrations. Existing patient records are never reset."""
from backend.app.store import now


def _column_exists(db, table: str, column: str) -> bool:
    return any(row["name"] == column for row in db.execute(f"PRAGMA table_info({table})"))


def _add_column(db, table: str, definition: str) -> None:
    """SQLite does not support ADD COLUMN IF NOT EXISTS."""
    column = definition.split()[0]
    if not _column_exists(db, table, column):
        db.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def migrate(db):
    db.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
    if not db.execute('SELECT 1 FROM schema_migrations WHERE version=1').fetchone():
        db.execute('CREATE TABLE IF NOT EXISTS ai_summaries(summary_id TEXT PRIMARY KEY, encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id), revision INTEGER NOT NULL, provider TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL, created_by TEXT NOT NULL REFERENCES users(user_id))')
        db.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(1,?)', (now(),))
    if not db.execute('SELECT 1 FROM schema_migrations WHERE version=2').fetchone():
        db.execute('CREATE TABLE knowledge_sources(source_id TEXT PRIMARY KEY,title TEXT NOT NULL,source_url TEXT NOT NULL,content_hash TEXT NOT NULL,approved_by TEXT NOT NULL REFERENCES users(user_id),approved_at TEXT NOT NULL,enabled INTEGER NOT NULL)')
        db.execute('CREATE TABLE knowledge_chunks(chunk_id TEXT PRIMARY KEY,source_id TEXT NOT NULL REFERENCES knowledge_sources(source_id),ordinal INTEGER NOT NULL,text TEXT NOT NULL,embedding_json TEXT NOT NULL,embedding_model TEXT NOT NULL)')
        db.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(2,?)',(now(),))
    if not db.execute('SELECT 1 FROM schema_migrations WHERE version=3').fetchone():
        # Keep the original document intact while making each page and each extracted
        # statement independently reviewable.  These columns are additive so existing
        # local demo databases continue to work without a reset.
        _add_column(db, 'encounters', "care_mode TEXT NOT NULL DEFAULT 'MODERN'")
        _add_column(db, 'documents', 'document_date TEXT')
        _add_column(db, 'documents', 'classification_confidence REAL')
        _add_column(db, 'documents', 'processing_detail_json TEXT')
        _add_column(db, 'reconciliation_items', 'document_id TEXT')
        _add_column(db, 'reconciliation_items', 'page_number INTEGER')
        _add_column(db, 'reconciliation_items', 'evidence TEXT')
        _add_column(db, 'timeline_events', 'document_id TEXT')
        _add_column(db, 'timeline_events', 'page_number INTEGER')
        _add_column(db, 'timeline_events', "verification_status TEXT NOT NULL DEFAULT 'REPORTED'")
        _add_column(db, 'timeline_events', "metadata_json TEXT NOT NULL DEFAULT '{}'")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS document_pages (
                document_page_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL CHECK(page_number > 0),
                raw_text TEXT NOT NULL,
                extraction_method TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                created_at TEXT NOT NULL,
                UNIQUE(document_id, page_number)
            );
            CREATE TABLE IF NOT EXISTS document_entities (
                entity_id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL REFERENCES documents(document_id) ON DELETE CASCADE,
                page_number INTEGER NOT NULL CHECK(page_number > 0),
                entity_type TEXT NOT NULL,
                field_name TEXT,
                value_json TEXT NOT NULL,
                normalized_value TEXT,
                evidence TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence BETWEEN 0 AND 1),
                verification_status TEXT NOT NULL CHECK(verification_status IN ('NEEDS_VERIFICATION','VERIFIED','REJECTED')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS ix_document_entities_document ON document_entities(document_id, page_number);
            CREATE INDEX IF NOT EXISTS ix_document_entities_field ON document_entities(field_name, normalized_value);
            CREATE TABLE IF NOT EXISTS follow_up_plans (
                follow_up_plan_id TEXT PRIMARY KEY,
                patient_id TEXT NOT NULL REFERENCES patients(patient_id),
                encounter_id TEXT NOT NULL REFERENCES encounters(encounter_id),
                instructions TEXT,
                follow_up_at TEXT,
                status TEXT NOT NULL CHECK(status IN ('ACTIVE','COMPLETED','CANCELLED')),
                created_by TEXT NOT NULL REFERENCES users(user_id),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(encounter_id)
            );
            CREATE TABLE IF NOT EXISTS follow_up_sessions (
                follow_up_session_id TEXT PRIMARY KEY,
                follow_up_plan_id TEXT NOT NULL REFERENCES follow_up_plans(follow_up_plan_id) ON DELETE CASCADE,
                patient_id TEXT NOT NULL REFERENCES patients(patient_id),
                status TEXT NOT NULL CHECK(status IN ('ACTIVE','COMPLETED')),
                revision INTEGER NOT NULL DEFAULT 0,
                risk_level TEXT NOT NULL CHECK(risk_level IN ('LOW','MODERATE','HIGH','EMERGENCY')),
                started_at TEXT NOT NULL,
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS follow_up_responses (
                follow_up_response_id TEXT PRIMARY KEY,
                follow_up_session_id TEXT NOT NULL REFERENCES follow_up_sessions(follow_up_session_id) ON DELETE CASCADE,
                question_id TEXT NOT NULL,
                question_text TEXT NOT NULL,
                response_text TEXT NOT NULL,
                source TEXT NOT NULL CHECK(source IN ('PATIENT_REPORTED','VOICE_TRANSCRIPT')),
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS follow_up_alerts (
                follow_up_alert_id TEXT PRIMARY KEY,
                follow_up_session_id TEXT NOT NULL REFERENCES follow_up_sessions(follow_up_session_id) ON DELETE CASCADE,
                severity TEXT NOT NULL CHECK(severity IN ('MODERATE','HIGH','EMERGENCY')),
                message TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('OPEN','ACKNOWLEDGED','RESOLVED')),
                created_at TEXT NOT NULL,
                resolved_at TEXT,
                resolved_by TEXT REFERENCES users(user_id)
            );
            CREATE INDEX IF NOT EXISTS ix_follow_up_plans_patient ON follow_up_plans(patient_id, status);
            CREATE INDEX IF NOT EXISTS ix_follow_up_sessions_plan ON follow_up_sessions(follow_up_plan_id, started_at);
            CREATE INDEX IF NOT EXISTS ix_follow_up_alerts_status ON follow_up_alerts(status, severity);
            """
        )
        db.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(3,?)',(now(),))
    if not db.execute('SELECT 1 FROM schema_migrations WHERE version=4').fetchone():
        _add_column(db, 'document_entities', "entity_metadata_json TEXT NOT NULL DEFAULT '{}'")
        db.execute('INSERT INTO schema_migrations(version,applied_at) VALUES(4,?)',(now(),))
