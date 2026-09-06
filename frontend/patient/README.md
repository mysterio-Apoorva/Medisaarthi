# MEDISAARTHI Patient Frontend (M1)

This is the M1 module for the patient-side flow. It is intentionally a clean UI client over the interview API that M2 owns now and M3 can proxy later.

## What this module does

- Collects patient ID, name, age, gender
- Language selection (English / Hindi)
- Consent capture
- Shows interview questions from M2 (`next_question.text`)
- Sends answers as text
- Uses browser speech-to-text for voice input (Web Speech API)
- Plays AI question with browser speech synthesis (optional, controlled by env)
- Shows progress and missing fields from M2 state
- Ends interview and shows collected clinical snapshot

## How it connects to M2

The frontend calls the following M2 endpoints:

- `POST /interview/start`
- `POST /interview/respond`
- `POST /interview/complete`

Every mutation uses `expected_revision` from the latest response for safe updates.
If a stale update returns `409`, the UI refreshes the current interview without silently
replaying the patient's answer.

## Run locally

```powershell
cd C:\Users\anura\Desktop\SIH\m2-conversational-ai\frontend\patient
npm install
copy .env.example .env.local
npm run dev
```

Use `http://localhost:3000`.

## Backend requirement

Start M2 API on `http://127.0.0.1:8000`. For real extraction, configure M2:

```text
M2_LLM_PROVIDER=gemini
GEMINI_API_KEY=<your-google-ai-studio-key>
GEMINI_MODEL=gemini-3.6-flash
```

If you run with `M2_LLM_PROVIDER=mock`, responses will be from the demo parser.

## Browser support

Voice input uses browser speech APIs:

- `SpeechRecognition` / `webkitSpeechRecognition`
- `speechSynthesis`

If unavailable, users can continue with typed input.

## Files to understand first

- `src/app/page.tsx` – all M1 screens and workflow
- `src/lib/api.ts` – API client contract and request handling
- `src/lib/contracts.ts` – shared data types used in UI state
- `frontend/patient/.env.example` – local configuration

## M3/M4 compatibility note

Set `NEXT_PUBLIC_API_BASE_URL` to M3's gateway when it is ready. The older
`NEXT_PUBLIC_M2_API_BASE_URL` name remains supported for local setups. This M1 module
is only consuming M2 response contracts. No patient database, no
doctor workflow, and no clinical summary model is implemented here. M3 can later
replace API base host without changing frontend behavior.
