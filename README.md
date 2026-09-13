# MediKiosk / Medisaarthi

MediKiosk is an AI-assisted, clinician-supervised pre-consultation intake platform. It turns a patient conversation into a structured history, runs deterministic safety and completeness checks, keeps each fact's provenance, and hands unresolved document conflicts to the clinician for review. It is not a diagnostic system and never replaces emergency care or clinician judgment.

## What is demonstrably working

- Patient registration and session-based sign-in; role-checked patient, doctor, and administrator access.
- A persisted conversational encounter: consent, adaptive questions, structured facts, completeness, deterministic red flags, patient submission, and clinician finalization.
- An actual document pipeline for PDF, JPEG, PNG, and WebP (10 MB limit): validation, local storage, PyMuPDF text extraction or Tesseract OCR where installed, provenance, and a reconciliation queue. Unreadable files are marked `NEEDS_REVIEW`; no text is invented.
- A doctor queue, structured encounter view, correction endpoint, reconciliation decisions, timeline events, and privacy-conscious audit records.
- A runnable synthetic chest-pain safety scenario that verifies the complete patient-to-admin workflow.

Synthetic seed identities are solely for an SIH demonstration and are visibly labelled in the UI. They are stored in the local database, not injected by the frontend.

See the [engineering report](docs/ENGINEERING_REPORT.md) for bugs fixed, actual test evidence and explicit remaining scope. This is a tested local demonstration, not a claim that every requested clinical or hospital-integration feature is finished.

## Architecture

```text
Next.js patient / doctor UI
        | authenticated fetch with HttpOnly session cookie
FastAPI routes -- SQLite relational store
        |              |
        |              +-- encounters, answers, facts, consents, documents
        |              +-- red flags, reconciliation, timeline, audit
        |              +-- users / assignments / server sessions
        |
AI provider abstraction -- Ollama (optional) / explicit clinical-rules fallback
        |
Clinical engine: ontology -> state machine -> adaptive questions
                 -> red flags -> completeness -> factual summary
```

The core workflow is intentionally deterministic. The model is used only for language extraction and must return schema-validated, evidence-grounded facts. Authentication, authorization, state changes, completion, and red-flag rules are ordinary server-side code.

## Technology choices

| Area | Current implementation | Why |
|---|---|---|
| Web client | Next.js 16, React 19, TypeScript, existing MediKiosk UI | Preserves the existing visual language and routes. |
| API | FastAPI + Pydantic | Typed request validation and straightforward local execution. |
| Persistence | SQLite, normalized tables, foreign keys | Zero-cost, durable demo setup; `DATABASE_URL` supports a SQLite path. |
| Conversational model | Ollama `qwen2.5:3b-instruct` when locally installed | Free, local, structured JSON-capable, and replaceable. |
| Fallback | Explicit `clinical_rules` provider | The intake remains available if Ollama is unavailable; it is reported as rules, not AI. |
| Documents | PyMuPDF, Pillow, Tesseract or bundled RapidOCR | Local PDF and image/scanned-PDF OCR; unreadable files stay available for manual review. |
| Voice | Browser `MediaRecorder` + local faster-whisper API | Uploaded microphone bytes are transcribed server-side; typing remains available if speech is unavailable. |
| Talking avatar | SVG character + Web Audio + local Piper | Mouth opening is driven by real audio amplitude; local device speech is a fallback. |
| References | Ollama `all-minilm` embeddings + SQLite chunks | Optional source-grounded retrieval; patient records are never indexed. |

Larger Qwen3, Llama, Mistral, and Gemma models were considered, but were not benchmarked against this machine. The existing installed Qwen2.5 3B model was retained after real local inference tests: it is small enough for this demo and supports constrained JSON. This is a practical selection, not a claim of medical-model superiority. `AIProvider` exposes generation, schema-constrained output, allowlisted tool-call requests, and embeddings. `AI_FALLBACK_MODELS` optionally supplies additional installed Ollama models; failed providers enter bounded cooldowns. External model destinations require `ALLOW_EXTERNAL_AI=true`.

## Clinical engine and agents

`backend/app/clinical_engine.py` owns an extensible starter ontology for chest pain, headache, fever, cough, abdominal pain, vomiting, diarrhea, breathlessness, dizziness, and fatigue. It owns interview stages, question selection, red-flag evaluation, completeness, and factual summaries. It does not assume missing values.

`backend/app/ai/orchestrator.py` coordinates executable intake, question, safety, summarization, and document agents. Intake invokes validated local-model extraction. Question and safety agents use deterministic tools; they do not waste separate model calls on permissions or clinical rules. Summarization asks the model to organize existing fact IDs, rejects invented references, preserves omitted facts, and persists the result against the encounter revision. The older narrative remains a deterministic structured-record rendering, not an AI-generated summary. Document extraction uses real local PDF/OCR and conservative medication/allergy patterns; it does not claim unrestricted medical-report interpretation. Conflicting facts enter reconciliation instead of silently replacing current values.

## Document intelligence, AYUSH, and follow-up

### Documents become reviewable clinical sources

The patient review screen accepts multiple PDFs, JPEGs, PNGs, and WebP images in one selection. Each file is signature-checked and retained in protected local storage. PDF text is extracted with PyMuPDF; image/scanned-page text is extracted with Tesseract where installed or local RapidOCR otherwise. The system records each page, extraction method, OCR confidence, original evidence snippet, document date when an explicit date can be parsed, and a conservative classification such as Prescription, Laboratory Report, Discharge Summary, Radiology Report, or AYUSH Consultation Note.

The local document-review agent uses source-text patterns to find explicitly written medications, allergies, diagnoses, procedures, vitals, investigations, and printed dates. It never fills missing values. A laboratory value is labelled low or high only when that document also contains a numeric reference range. Every extracted item remains `NEEDS_VERIFICATION`; document candidates create reconciliation entries rather than replacing interview facts. Matching document events are added to the chronological timeline with document ID, page, evidence, confidence, and verification status. The patient and clinician can inspect the original, per-page text, entity evidence, processing steps, retry a failed extraction, and remove an unfinalized upload.

### AYUSH history mode

At language selection, choose **Modern medicine** or **AYUSH / Ayurveda**. AYUSH mode adds persisted, patient-reported Dashavidha Pariksha and Ahara-Vihara fields: Prakriti, Vikriti, Sara, Samhanana, Pramana, Satmya, Sattva, Ahara Shakti, Vyayama Shakti, Vaya, Ahara-Vihara, Nidana, and Samprapti. These answers are identified as patient reports in the review and summary; they are not AI diagnoses or practitioner assessments. AYUSH-related documents can also be classified for clinician review.

### Follow-up agent

Clinician finalization creates one persisted follow-up plan for the finalized encounter. The clinician can record optional instructions and a suggested date in the verification dialog; the service never invents instructions. A patient opens `/patient/follow-up` to answer a condition-aware check-in. Questions are selected from the finalized complaint, recorded medicines, and clinician-entered instructions. The same SVG avatar can speak the live question, and actual microphone audio can be transcribed through local Whisper into an editable draft before saving.

Follow-up responses, risk level, and alerts are stored relationally and added to the patient timeline. Deterministic rules escalate chest symptoms with breathing difficulty, fainting, severe bleeding, worsening/severe symptoms, and medication-adherence/possible-side-effect concerns. Clinicians see the last check-in, latest response, open alert, and acknowledgement control in the encounter review. The agent does not diagnose, prescribe, or change medication.

## Security, consent, and audit

- Passwords use `scrypt`; sessions are server-side, hashed, and issued as HttpOnly, SameSite cookies.
- API RBAC is enforced on the server. Patients can access only their own records; doctors can access only assigned patients; administrators have explicit routes.
- Request schemas, file allow-lists, filename sanitization, size limits, strict CORS configuration, safe error responses, optimistic encounter revisions, and SQL parameterization are used.
- Consent is a row with type, version, purpose, actor, timestamp, and status. Clinical intake and document-processing consent are separate.
- Audit records cover login, consent, encounter changes, document work, clinician corrections, reconciliation, finalization, and selected record access. Raw clinical answer text is not copied into audit metadata.

## Interoperability and RAG

The doctor screen downloads a real local FHIR R4 collection via `backend/app/fhir_export.py`: Patient, Encounter, Observation, historical Condition, Medication/MedicationStatement, AllergyIntolerance, DocumentReference, and Consent are generated only from recorded data. References and encounter statuses are mapped to R4 shapes. Full implementation-guide/conformance validation is still required. The legacy ABDM/HIS development mappers in `integrations.py` are not live connectors and are not an ABDM certification claim.

`backend/app/routes/knowledge.py` provides actual admin-approved ingestion, local embeddings, persisted chunks, cosine retrieval, and optional model selection of exact source excerpts. The server validates every selected quote against the retrieved text. The doctor and admin screens expose it. There is deliberately no pre-approved clinical corpus; an administrator must supply authorized reference material. SQLite vector scanning is appropriate for a small demonstration corpus, not large-scale search. pgvector is not installed or claimed. The older `rag.py` helper is not used by the running workflow.

## Run locally

Prerequisites: Node.js 20+, Python 3.12+, and npm. Ollama is optional.

```powershell
# Frontend dependencies
npm install

# Backend virtual environment and dependencies
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# Real local language and reference models
ollama pull qwen2.5:3b-instruct
ollama pull all-minilm

# Real local English and Hindi speech output
backend\.venv\Scripts\python.exe -m piper.download_voices en_US-lessac-medium hi_IN-pratham-medium --download-dir backend/data/tts
```

Copy `backend/.env.example` to `backend/.env` if you need to override defaults. Copy `.env.example` to `.env.local` for the frontend. Start the applications in two terminals:

```powershell
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
npm run dev
```

Open `http://localhost:3000`. The FastAPI OpenAPI page is at `http://127.0.0.1:8000/docs`.

Synthetic demo credentials:

| Role | Email | Password |
|---|---|---|
| Patient | `patient.demo@medikiosk.local` | `DemoPass!2026` |
| Doctor | `doctor.demo@medikiosk.local` | `DemoPass!2026` |
| Admin | `admin.demo@medikiosk.local` | `DemoPass!2026` |

The local SQLite file is `backend/data/medikiosk.sqlite3`. It is initialized and seeded once; do not delete it unless you intentionally want to erase local synthetic/demo records.

## Environment variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLite URL/path; defaults to `backend/data/medikiosk.sqlite3`. |
| `AI_PROVIDER` | `ollama` or `clinical_rules`. |
| `AI_MODEL` / `OLLAMA_BASE_URL` | Local Ollama model and host. |
| `AI_SUMMARY_TIMEOUT` | Bounded local model-summary request timeout in seconds; default 75, maximum 120. |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed web origins; also checked for mutating browser requests. |
| `COOKIE_SECURE` | Set `true` behind HTTPS. |
| `DOCUMENT_UPLOAD_DIR` | Local protected document directory. |
| `FHIR_BASE_URL`, `ABDM_BASE_URL`, `HIS_BASE_URL` | Reserved integration configuration; no live connector is enabled by default. |
| `NEXT_PUBLIC_API_BASE_URL` | Defaults to `/api`, the same-origin Next.js proxy. |
| `BACKEND_INTERNAL_URL` | Server-side proxy destination, default `http://127.0.0.1:8000`. |
| `STT_MODEL`, `STT_MODEL_DIR`, `STT_DEVICE`, `STT_COMPUTE_TYPE` | Whisper defaults: multilingual `base`, `backend/data/models`, `cpu`, `int8`. First load downloads model weights if not cached. |
| `TTS_MODEL_EN`, `TTS_MODEL_HI` | Local Piper ONNX voice paths; see `backend/.env.example`. |
| `AI_FALLBACK_MODELS`, `ALLOW_EXTERNAL_AI`, `EMBEDDING_MODEL` | Optional installed-model priority, explicit external-data opt-in, and reference embedding model. |
| `MEDIKIOSK_DB_PATH`, `DEMO_PASSWORD`, `LOG_LEVEL` | SQLite path override, seed-only synthetic password, and server log level. |

No paid API key is required for development or the included demo.

## Verification

```powershell
# Core end-to-end proof: RBAC, consent, adaptive chest-pain intake,
# red flag, actual PDF extraction, reconciliation, doctor finalization, admin audit
backend\.venv\Scripts\python.exe backend\scripts\e2e_smoke.py

# Unit/security tests use an isolated synthetic database
backend\.venv\Scripts\python.exe -m pytest backend/tests -q -p no:cacheprovider

# Focused document page/entity, AYUSH, and follow-up integration checks
backend\.venv\Scripts\python.exe -m pytest backend/tests/test_document_followup_ayush.py -q -p no:cacheprovider

# Real browser microphone + avatar + patient/doctor/admin workflow (servers running)
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/browser_voice_e2e.py

# Real OCR, embeddings, grounded retrieval and summary (isolated database)
backend\.venv\Scripts\python.exe -X utf8 backend/scripts/local_ai_checks.py
npm run lint

# Real registration and administrator-authorized doctor assignment
backend\.venv\Scripts\python.exe backend/scripts/browser_registration_e2e.py

# Production client build
npm run build
```

The smoke test uses a new synthetic encounter on each run and does not depend on hardcoded API responses. It intentionally tests cross-patient access denial and a local-model failure fallback. A `StarletteDeprecationWarning` may appear from the installed test-client dependency; it does not indicate a failed flow.

## Presentation walkthrough

1. Sign in as the synthetic patient and grant the two clearly worded consents.
2. Start an English encounter; enter “I have chest pain since yesterday.”
3. Answer the adaptive questions naturally, including breathlessness. The safety banner and completion state update from the persisted facts.
4. Review and correct the collected record, upload a sample report, inspect its extracted text, then explicitly consent and submit. Document candidates remain pending clinician reconciliation.
5. Sign in as the synthetic doctor. Open the submitted record, review source/provenance, resolve document candidates, correct a fact, and finalize.
6. Sign in as the synthetic administrator and inspect the audit log.

## Current limitations

- SQLite is right for local/demo deployment, not a multi-site production topology. PostgreSQL migrations, encrypted object storage, backups, monitoring, threat modeling, clinical governance, and deployment hardening are required before real patient use.
- Ollama must be installed and serving the configured model for model-assisted extraction. Without it the UI shows a rules-fallback warning; it does not pretend a model responded.
- OCR uses Tesseract when available or local RapidOCR otherwise. English printed reports are the primary tested OCR case; handwriting and Hindi OCR accuracy are not guaranteed. Failed/empty extraction stays reviewable.
- The first voice request loads the configured local multilingual Whisper model. A microphone and an HTTPS/localhost browser context are required; non-speech, invalid, or oversized recordings are rejected rather than turned into text.
- FHIR export and ABDM/HIS development adapters are not certified/live integrations. The reference corpus requires explicit administrator approval.
- This is a pre-consultation aid, not a diagnosis or emergency service. Red flags require immediate human clinical review.

## Voice and avatar operation

Click **Listen** once to enable speech playback. Browser autoplay is not assumed. The SVG assistant has real listening/processing/speaking/waiting states, idle breathing/blinking, and mouth opening computed from Piper WAV audio via a Web Audio analyser. Starting recording stops speech. **Stop & Review** sends audio to local Whisper and places the transcript into an editable draft; only **Continue** saves it. Recordings stop automatically before two minutes; microphone tracks and requests are cleaned up when leaving the screen. Repeating a start request with the same consent resumes the same encounter.

If Piper fails, an installed local browser voice is used if available, with speech-boundary-driven approximate mouth motion. Otherwise the question stays readable and intake continues. This fallback does not silently use a remote browser voice. Browser tests inject synthetic PCM into Chromium's actual recording pipeline; they do not certify the physical microphone or speakers. Use Chrome or Edge on localhost/HTTPS for the live demonstration.

## Database migrations and deployment

Startup applies additive, numbered migrations in `backend/app/migrations.py`; `schema_migrations` records versions. No database reset is required. The SQLite file, private uploads, downloaded model weights and `.env` files are not committed. For a zero-cost demonstration, run the frontend, backend, Ollama, Piper and Whisper on this machine. Hosted free CPU/RAM limits may not support these models; no free-cloud capacity is promised. Before real patient use, add reviewed clinical protocols, secure deployment, encrypted storage/backups, retention/deletion policies, operational monitoring, and external security/conformance assessment.

## Model and software licensing

Review licenses before distribution. Piper is GPL-licensed; its voice weights have separate terms. The English lessac voice derives from [Blizzard/Lessac data](https://www.cstr.ed.ac.uk/projects/blizzard/2013/lessac_blizzard2013/license.html). Consult the downloaded model cards and [Piper project](https://github.com/OHF-Voice/piper1-gpl). This demo is not a claim that every voice/model is unrestricted for commercial redistribution. The local FHIR export follows [FHIR R4 resource definitions](https://hl7.org/fhir/R4/encounter.html), not an ABDM implementation-guide certification.
