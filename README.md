# MediKiosk / Medisaarthi

A local, clinician-supervised application for patient intake, documents, measurements, prescribing, finalized PDFs and follow-up. Clinical records live in SQLite; browser storage contains only navigation identifiers and UI preferences.

## Implemented workflow

Patient registration → consent → adaptive AI interview with actual speech recognition and a speaking avatar → patient review → document upload/OCR/source reconciliation → tests and vitals → assigned-doctor review → stored prescription and advice → immutable finalized record → generated A4 PDF → patient follow-up and clinician alerts.

The server enforces 5–10 answered questions, including an additional database constraint. It never asks question 11. AI failures are explicit; manual intake is an explicit patient choice, not a hidden substitute. Missing document text stays marked for review. Prescriptions contain doctor-entered medicine, dose, frequency, duration and route, or an explicit no-medicines reason.

Prescriptions also retain separate strength, medicine-specific instructions and the allergy information reviewed by the doctor. Changed allergy information requires renewed review before finalization. Record blood pressure as separate systolic/diastolic values. Height and weight calculate and persist BMI with links to the source measurements; withdrawing a source recalculates or withdraws its BMI. No diagnostic BMI category is generated.

## Run locally on Windows

Use Python 3.12 and Node 20 or newer. From the repository root:

```powershell
npm install
python -m venv backend/.venv
& backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

Create your local configuration from [backend/.env.example](backend/.env.example). Keep `SEED_DEMO_DATA=false` for a real empty installation. SQLite defaults to `backend/data/medikiosk.sqlite3`; uploaded documents default to `backend/data/uploads`. Use persistent absolute paths for a shared deployment.

Install and run a local Ollama service, then provision the models:

```powershell
ollama pull qwen2.5:3b-instruct
ollama pull all-minilm
& backend/.venv/Scripts/python.exe -m piper.download_voices en_US-lessac-medium hi_IN-pratham-medium --download-dir backend/data/tts
```

Whisper downloads its configured model on first use; preload it while connected if the kiosk must work offline:

```powershell
& backend/.venv/Scripts/python.exe -c "from backend.app.voice import _get_model; _get_model('en'); _get_model('hi')"
```

Provision real staff accounts explicitly (passwords are entered privately at the prompt; no patients or clinical records are seeded):

```powershell
& backend/.venv/Scripts/python.exe backend/scripts/create_staff.py --role ADMIN --email admin@your-clinic.example --name "Clinic Administrator"
& backend/.venv/Scripts/python.exe backend/scripts/create_staff.py --role DOCTOR --email doctor@your-clinic.example --name "Attending Doctor"
```

Use separate terminals for the API and web server:

```powershell
& backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
npm run dev
```

Open http://127.0.0.1:3000. New patients register through the patient portal. An administrator signs in at `/doctor/login`, opens `/admin`, and assigns the patient to a doctor. The doctor signs in with their own credentials. Assignment is required before that doctor can access the patient's records.

The frontend proxies `/api/*` to FastAPI. Set `BACKEND_INTERNAL_URL` if the backend address differs. For a shared deployment, configure HTTPS, secure cookies, allowed origins, protected filesystem access, backups and a reviewed operational security policy.

## Synthetic testing only

Demo records are isolated in [backend/demo_data.py](backend/demo_data.py). They are never silently injected into normal startup.

For a separate test database, explicitly run `backend/scripts/seed_data.py` or set `SEED_DEMO_DATA=true`. The browser acceptance runner expects the synthetic staff identities supplied by that seed. Never enable these public demonstration credentials on a shared clinical installation.

## Verification

```powershell
npm run lint -- --max-warnings 0
npm run typecheck
npm run typecheck:backend
npm run build
npm run test:unit
npm test
npm run test:legacy-client-contracts
npm run test:vad
npm run test:local-ai
npm run test:complete
```

The complete browser test requires the running web/API/local-model services and a separate seeded acceptance database. It registers a fresh synthetic patient through the UI; it does not inject answers, model output, extracted data or prescriptions into the application. Synthetic spoken WAV input replaces only physical microphone hardware; actual capture, VAD, ASR, model inference, TTS, avatar movement, OCR, database persistence and PDF rendering execute.

See [end-to-end evidence and reproduction](docs/END_TO_END_AUDIT.md), [all 59 endpoint contracts](docs/API_AUDIT.md), and [OpenAPI request schemas](docs/api-openapi.json). The endpoint report can be regenerated with `backend/scripts/audit_endpoints.py` after the unit, local-AI and complete-browser tests pass.

The [shutdown recovery audit](docs/RESUME_AUDIT.md) distinguishes the pre-existing implementation from the verified gaps repaired during recovery. Runtime databases, logs and generated acceptance documents are excluded from Git.

## Boundaries

This is not autonomous diagnosis or prescribing. Clinicians must verify extracted information; transcription and OCR can misread source material. Rule-based safety flags and document recognizers are bounded implementations, not a guarantee of medical accuracy. Manual measurements require an actual measured source; there is no connected medical-device driver. The FHIR download is a local export, not a live hospital/ABDM connection. Physical audio hardware, deployment security and clinical suitability require on-site validation.
