# MediKiosk engineering handoff

Historical report. Current implementation and verification: [END_TO_END_AUDIT.md](END_TO_END_AUDIT.md) and [API_AUDIT.md](API_AUDIT.md).

Verification date: 13 September 2026. This is a tested local demonstration build, not a production-readiness, clinical-validation, or live hospital-integration certification. The complete requested specification is not claimed finished; remaining boundaries are listed below.

## Existing work preserved

The starting workspace already ran Next.js 16 / React 19 / TypeScript with FastAPI, a relational SQLite store, cookie authentication, role boundaries, patient/doctor screens, deterministic clinical intake, a local Qwen model, faster-whisper and PDF processing. The existing blue/teal visual language, cards, navigation, responsive layouts, API-backed patient queue and authentication were retained. The large pre-existing worktree changes were not reset. No patient database was deleted or recreated.

## Bugs fixed and integration changes

- Voice previously submitted immediately and left the client revision stale. Recording now produces a real Whisper transcript in an editable draft; only Continue submits it through the same validated answer API as typed input.
- Added microphone permission/unsupported-browser errors, safe recording MIME selection, bounded recording duration, track cleanup, abort handling and interruption of assistant speech before recording. Failed sends retain the patient's draft.
- Repeated encounter initialization/refresh now reuses the encounter attached to that consent. Removed the client fallback to a fixed patient ID.
- Fixed negation boundaries, unknown answers incorrectly becoming positive, durations becoming severity scores, arbitrary severity types, and negative substrings incorrectly emptying medication lists.
- Replaced estimated progress and discarded flags with server-calculated completeness and safety results. Changed-answer corrections recompute the interview stage. Concurrent answers use revision checks before persistence.
- Added patient record review, typed corrections, real report upload/extraction review and versioned submission consent. Blocked incomplete critical submission, repeat submission and updates/uploads after finalization.
- Connected doctor document downloads, extracted text, fact provenance, reconciliation, longitudinal events, actual local-model summaries and local FHIR download to their APIs.
- Doctor finalization now requires a submitted record with required information and resolved conflicts. Corrections and reconciliation decisions are validated and audited. Fixed priority ordering and status badges.
- Removed misleading static verification/active-session labels and fake model/quality labels. Zero severity and explicitly empty histories no longer look unrecorded.
- Added explicit administrator-to-doctor patient assignment and validated ontology extensions that actually affect question selection.
- Fixed same-origin API configuration and the proxy timeout for bounded local model work. Loaded backend environment configuration before resolving persistent paths.
- Added origin checks, upload bounds/signature checks, rate limiting, safe client errors, privacy-conscious request metadata, failed-login auditing and expired-session logout handling.

## Final architecture and technologies

```text
Existing Next.js patient / doctor / admin screens
  -> same-origin /api proxy + HttpOnly session
  -> FastAPI authorization + typed validation
  -> SQLite relational record + optimistic encounter revision
  -> clinical orchestrator and deterministic engine
  -> optional local model / OCR / speech / reference retrieval
  -> validated facts, provenance, conflicts and audit
  -> patient review / clinician review / finalization
```

SQLite uses foreign keys, WAL, a busy timeout and additive numbered migrations. Users, assignments, sessions, patients, encounters, answers, individual facts, documents/extractions, consents, flags, reconciliation items, timeline and audit records are relational; histories are not a single replaceable conversation JSON blob. Additional tables persist revision-bound summaries and approved reference chunks. This is not a PostgreSQL/pgvector deployment.

### Models, agents and provider routing

Retained the installed Ollama `qwen2.5:3b-instruct` after actual extraction and summary inference. Its local footprint and constrained JSON support suit the current demonstration machine. Qwen3, Llama, Mistral and Gemma were considered but not comparatively benchmarked; no superior medical accuracy is claimed. `all-minilm` supplies real local embeddings.

`AIProvider` exposes generation, structured output, allowlisted tool-call requests and embeddings. The provider manager tracks failures, observed latency and bounded cooldowns, tries optionally configured installed models and reports an explicit deterministic fallback. This is local model routing, not tested multi-vendor free-tier failover. External destinations require explicit configuration.

The orchestrator invokes executable intake, question, safety, summarization and document agents. The question and safety agents use deterministic tools. Summary generation is deliberately constrained: Qwen organizes validated fact identifiers, then the server renders the original recorded values. Unknown identifiers are rejected, duplicate references are deduplicated, and omitted facts remain visible. This is real model-assisted organization, not unrestricted narrative diagnosis generation.

The clinical engine supplies ten starter complaint concepts, adaptive required-field selection, history stages, safety prioritization and completeness. Its rules are deterministic, not hardcoded patient outcomes. Admin ontology extensions are additive so they cannot silently remove built-in requirements.

### Avatar, TTS and STT

An original lightweight SVG avatar is integrated into the interview. Real Piper WAV audio feeds a Web Audio analyser; measured audio amplitude drives visible mouth opening. Listening, thinking, speaking and waiting states follow actual workflow state. Idle breathing/blinking respects reduced-motion preferences. There is no looping mouth animation pretending to be audio analysis.

Local Piper voices: `en_US-lessac-medium` and `hi_IN-pratham-medium`. If unavailable, an installed local browser voice can be used with approximate boundary-driven mouth movement; if that also fails, readable text remains available. Playback requires a user gesture. Voice/model redistribution licenses must be reviewed separately.

MediaRecorder uploads actual recorded bytes to multilingual faster-whisper `base`, CPU/int8. Signature, size and duration checks precede transcription. Silence produces an error, not a fabricated answer. Browser tests inject clearly synthetic audio into Chromium's actual capture pipeline; physical microphone quality and speaker output still require a device check.

### Documents and references

PyMuPDF extracts PDF text. Images and scanned pages use installed Tesseract or local RapidOCR. Protected originals and extraction evidence remain accessible to authorized reviewers. Conservative medication/allergy candidates enter reconciliation; unreadable files remain marked for manual review. This is not a general validated parser for every medical report or handwriting style.

Optional RAG has actual approved-source ingestion, local embeddings, persisted chunks, cosine retrieval and model-selected excerpts validated against source text. Results expose source URLs/hashes and chunk identifiers. Patient data is not the reference corpus. The initial corpus is empty; the real-model acceptance test uses explicitly synthetic material in an isolated database.

### Identity, consent, audit and interoperability

Passwords use scrypt; server-side sessions use hashed tokens and HttpOnly cookies. Patient ownership, doctor assignment and administrator privileges are enforced by the API. Consent records capture purpose/version/status/actor/time, including explicit reviewed-record submission. Audits include access, processing, edits, reconciliation and finalization without copying raw answers into audit metadata.

The clinician downloads a functional local FHIR R4 collection of recorded Patient, Encounter, Observation, historical Condition, Medication/MedicationStatement, AllergyIntolerance, DocumentReference and Consent data. Basic resource/reference invariants were tested, not full implementation-guide conformance. ABDM/HIS modules remain isolated offline development mappers: no live connection, certified consent exchange or comprehensive HIS synchronization is claimed.

## Verification evidence

| Check | Result and scope |
|---|---|
| Production frontend build | Passed, including TypeScript and generation of all 15 route pages |
| Lint | `npm run lint -- --quiet` passed with zero errors; inherited warnings are not claimed eliminated |
| Backend tests | 23 passed; dependency deprecation warnings remain |
| API workflow | `npm test` passed with real local Ollama, real PDF extraction, silence rejection, clinical state, consent, doctor reconciliation/correction/finalization and admin audit |
| Full browser workflow | Passed in real Edge: patient login, consent, refresh reuse, actual Piper playback/mouth movement, MediaRecorder to Whisper, transcript correction, adaptive answers, review, PDF extraction, submission, doctor model summary/reconciliation/FHIR/finalization and admin audit |
| Registration/authorization browser check | Passed: new patient registration, cross-patient denial, unassigned-doctor denial, admin assignment and assigned-doctor access |
| Local AI acceptance | Passed: actual image OCR, embeddings, persisted reference retrieval, grounded excerpts and fact-ID summary; isolated synthetic database |
| Visual persistence/mobile check | Passed: fresh-login finalized record, disabled finalization button, 390px layout without document overflow, no browser runtime errors |
| Running services | Frontend HTTP 200 at port 3000; backend health reports SQLite and Ollama at port 8000 |

Failure tests explicitly cover malformed/unsupported model output, model unavailability, Whisper/TTS unavailability, embedding outage, safe database-health failure, stale/empty answers, expired sessions, cross-patient access, authorization, forged/oversized uploads, source conflicts and lifecycle/consent gates. Controlled failure tests use test doubles; the separate browser/local-AI acceptance runs use actual inference. This is not exhaustive fault-injection coverage for every device, language or concurrency schedule.

The first finalized screenshot accidentally caught a refresh spinner; its assertion was strengthened and the final chart rechecked. A visual check run concurrently with an API test observed the newly active encounter instead of a finalized one; rerunning after that test completed passed. Evidence is not represented as a first-try, failure-free build.

## Exact local commands and configuration

From the repository root, use the detailed installation instructions and full environment table in [README](../README.md). No paid account or API key is required. Ollama, model downloads, local OCR/TTS/STT and Edge browser testing are the free local services used; no free-cloud capacity is promised.

```powershell
npm install
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
ollama pull qwen2.5:3b-instruct
ollama pull all-minilm
backend\.venv\Scripts\python.exe -m piper.download_voices en_US-lessac-medium hi_IN-pratham-medium --download-dir backend/data/tts

# Separate terminals, from the repository root:
backend\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
npm run dev

# Servers must be running for browser checks; run workflow scripts sequentially.
npm run test:unit
npm test
npm run test:browser
backend\.venv\Scripts\python.exe backend/scripts/browser_registration_e2e.py
npm run test:local-ai
npm run lint -- --quiet
npm run build
```

Configure `backend/.env` from its example and `.env.local` from the root example. Important settings are `MEDIKIOSK_DB_PATH`, `NEXT_PUBLIC_API_BASE_URL=/api`, `BACKEND_INTERNAL_URL`, `AI_PROVIDER`, `AI_MODEL`, `OLLAMA_BASE_URL`, `AI_SUMMARY_TIMEOUT`, `AI_FALLBACK_MODELS`, `ALLOW_EXTERNAL_AI`, `EMBEDDING_MODEL`, STT/TTS paths, upload directory, CORS origins, cookie security and the seed-only demo password. Startup applies migrations without clearing existing data. Whisper downloads its weights on first use if not cached.

Synthetic accounts: `patient.demo@medikiosk.local`, `doctor.demo@medikiosk.local`, `admin.demo@medikiosk.local`; local default password `DemoPass!2026`. Change credentials before a shared deployment. Test scripts intentionally add labelled synthetic records to the local demo database; private uploads, model weights, screenshots and database files are ignored by Git.

## Remaining limitations and final audit

- The clinical rules and extraction accuracy need clinician-led validation. No diagnosis, measured doctor time-saving claim, or calibrated medical confidence is asserted.
- Unknown/declined required answers can still require clarification instead of a complete clinician-handoff path. Complex narratives, multiple simultaneous complaints and multilingual accuracy need broader evaluation. English is the end-to-end tested voice case.
- Administrator ontology/role/assignment/reference controls work; there is not yet a complete clinical question/red-flag rule-authoring and governance interface.
- Document candidates carry source types and extraction evidence, but reconciliation needs finer document/page linkage. Some storage/database failure sequences can leave an orphaned uploaded file; retention and cleanup need hardening.
- No live ABDM/HIS connector, PostgreSQL migration, pgvector service or full FHIR conformance certification is delivered.
- Physical microphone/speaker verification, cross-browser/device testing, production encryption/key management, backups, retention policies, regulatory assessment and external security review remain required before real patient use.
- Repository audit found ordinary HTML input placeholders plus older inactive M2 mock/Gemini modules and a legacy RAG helper. The active application imports the new orchestrator/provider/routes, not those mock paths. They were preserved rather than silently deleting unrelated existing work. Legacy source-text tests are not substitutes for the browser acceptance tests.

The demonstrated patient-to-clinician path is working with real local processing. These limitations are explicit unfinished scope, not hidden behind success messages or a production-ready label.
