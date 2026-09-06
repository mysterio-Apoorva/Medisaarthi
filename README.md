# MEDISAARTHI

An end-to-end SIH Round 1 MVP for AI-assisted hospital pre-consultation. A patient gives
consent and completes an adaptive English/Hindi interview; the application stores the
structured interview and longitudinal history in SQL; a doctor reviews, edits, and
approves a generated clinical briefing.

This application organizes patient-reported information. It does not diagnose,
prescribe, or replace physician judgment.

## Current project status — implemented up to now

The repository currently delivers the complete Round 1 patient-to-doctor workflow:

```text
Patient identification and consent
  → adaptive Gemini interview
  → structured clinical facts with source evidence
  → durable patient/interview/history storage
  → merged clinical summary and timeline
  → authenticated doctor review
  → physician edit and approval
```

Implemented capabilities:

- Patient web flow: welcome → language → consent → identity → text/voice interview → completion
- Real Gemini structured extraction for natural English, Hindi, and transliterated Hindi
- Deterministic clinical question graph for chest pain, fever, headache, abdominal pain,
  and a generic pathway
- Durable SQLite tables for patients, interviews, history, medications, allergies,
  summaries, doctor accounts, and sessions
- Physician dashboard with a live patient queue, clinical summary, past history,
  medications, allergies, source interview, evidence timeline, editing, and approval
- First-run doctor account creation with PBKDF2 password hashing and expiring bearer sessions
- Optimistic revision/version checks for concurrent interview and summary changes
- JSON Schema contracts generated from the runtime Pydantic models

Current boundaries:

- The system supports English and Hindi and four dedicated complaint pathways, with a
  generic pathway for other complaints.
- Speech recognition and question playback use browser speech APIs; no audio recording
  is stored by the backend.
- Existing medical history is entered or imported through the history API. The project
  deliberately does not invent or automatically seed medical records.
- The self-contained MVP uses SQLite. A PostgreSQL/Supabase repository adapter remains
  a deployment step for a hospital environment.
- This is pre-consultation information support, not diagnosis, triage certification,
  prescription generation, or production EHR/ABDM integration.

The teammate repository `Aryanuo/SIH` supplied the original M3 patient/history data
model and API direction. Its Supabase routes were reconciled with the existing adaptive
engine instead of being run as a second, incompatible interview service.

## Architecture

```text
Patient UI (/) ──┐
                 ├── FastAPI ── Interview engine ── Gemini
Doctor UI (/doctor) ─┘    │
                          └── SQLite durable clinical database
                                ├── patient/history
                                ├── structured interviews + evidence
                                ├── summaries + timeline
                                └── doctor auth + verification
```

The web UI never manufactures interview replies or patient summaries. The backend's
production composition uses Gemini and durable SQL. `MockProvider` and the in-memory
store remain only as explicit test fixtures so automated tests are deterministic and do
not spend API quota.

## Run locally

Requirements: Python 3.11+, Node.js 20+, and a Gemini API key.

```powershell
cd C:\Users\anura\Desktop\SIH\m2-conversational-ai
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in `.env`. `MEDISAARTHI_DB_PATH` is optional; without it, the
database is created at `data/medisaarthi.db`.

Start the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal, start the shared patient/doctor frontend:

```powershell
cd frontend\patient
npm install
npm run dev
```

Open:

- Patient application: http://localhost:3000
- Doctor dashboard: http://localhost:3000/doctor
- API documentation: http://127.0.0.1:8000/docs

On the first visit to `/doctor`, create the first physician account. That account is
written to the database; there are no embedded demo credentials. Subsequent visits use
the login screen.

## Continuous demo workflow

1. Open `/` and complete identification, consent, and an interview.
2. The patient identity and every structured turn are committed to the SQL database.
3. Completion merges the current interview with that patient's existing history and
   creates a draft clinical summary.
4. Open `/doctor`, sign in, and select the completed patient.
5. Review the briefing, clinical timeline, and full source interview.
6. Edit any generated text if necessary, save it, and approve the final summary.

History is real persisted data. It can be entered or imported through
`PUT /patients/{patient_id}/history`; empty history is shown honestly as empty rather
than being replaced with a hardcoded sample record.

## API

Patient and history:

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/patients` | Create or update a patient record |
| `GET` | `/patients` | List persisted patients |
| `GET` | `/patients/{patient_id}` | Get patient demographics |
| `GET` | `/patients/{patient_id}/history` | Get conditions, medications, allergies |
| `PUT` | `/patients/{patient_id}/history` | Replace structured history transactionally |

Interview:

| Method | Route | Purpose |
| --- | --- | --- |
| `POST` | `/interview/start` | Record patient/consent and start adaptive interview |
| `POST` | `/interview/respond` | Extract facts, persist evidence, return next question |
| `POST` | `/interview/complete` | Close interview and generate physician briefing |
| `GET` | `/interview/{interview_id}` | Get current patient-facing interview state |
| `GET` | `/interview/{interview_id}/record` | Get the complete structured source record |

Doctor authentication and review:

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/auth/status` | Check whether first-run doctor setup is needed |
| `POST` | `/auth/setup` | Create the first doctor account once |
| `POST` | `/auth/login` | Create an expiring doctor session |
| `GET` | `/doctor/patients` | Get the live patient review queue |
| `GET` | `/doctor/patients/{id}/summary` | Get a doctor-ready merged summary |
| `GET` | `/doctor/patients/{id}/timeline` | Get source/date/confidence timeline events |
| `PUT` | `/doctor/interviews/{id}/summary` | Save physician edits |
| `POST` | `/doctor/interviews/{id}/approve` | Approve a versioned summary |

Doctor routes require `Authorization: Bearer <access_token>`.

## Contracts and storage

Canonical wire contracts are in `contracts/`, including patient, interview, history,
clinical summary, and timeline schemas. Regenerate them after model changes:

```powershell
.\.venv\Scripts\python.exe -m examples.export_contracts
```

The SQL schema is created idempotently on startup by `app/persistence.py`. Interviews
are stored as validated versioned JSON plus indexed identity/status columns. Facts retain
their exact patient-statement evidence. Timeline confidence describes source certainty,
not diagnostic confidence.

For a deployed hospital system, replace the `SQLiteRepository` boundary with PostgreSQL,
put FastAPI behind TLS, add institution identity/roles and audit policy, and complete
clinical validation. None of those future changes require changing the interview wire
contract.

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
cd frontend\patient
npx tsc --noEmit
npm run build
```

The test suite covers adaptive extraction, safety behavior, wire-contract drift, durable
restart persistence, history merging, protected doctor access, physician edits,
approval, and timeline generation.

## Repository map

```text
app/
  api/main.py              unified FastAPI routes
  interview/               adaptive graph, schemas, engine, state transitions
  llm/                     Gemini structured-output adapter and test provider
  persistence.py           durable SQL repository and schema
  clinical.py              conservative doctor-summary composition
  auth.py                  first-run doctor setup and session authentication
  records.py               history/summary/timeline/auth contracts
frontend/patient/
  src/app/page.tsx         patient application
  src/app/doctor/page.tsx  physician dashboard
contracts/                 generated JSON Schemas
tests/                     domain, API, contract, persistence, and workflow tests
docs/                      integration notes
```
