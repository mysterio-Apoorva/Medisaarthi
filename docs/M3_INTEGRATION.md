# M3 integration contract

M1 and M2 are usable now, but M2's default process is intentionally a demo:

- `M2_LLM_PROVIDER=mock` uses a small deterministic parser.
- `M2_LLM_PROVIDER=gemini` uses Google Gemini structured extraction.
- The default `InMemoryInterviewStore` loses interviews when the process restarts.
- `GET /health` reports both choices so demos cannot accidentally present mock mode as live AI.

M3 owns patient identity, authorization, consent retention, and durable data. It should
not duplicate the question graph or extraction logic.

## Recommended composition

Implement the existing synchronous `InterviewStore` protocol in
`app/interview/state.py` using M3's transaction layer, then inject it:

```python
from app.api.main import create_app
from app.config import build_service

store = PostgresInterviewStore(session_factory)
service = build_service(store=store)
app = create_app(service)
```

The store has three operations:

```python
def create(interview: Interview) -> None: ...
def get(interview_id: str) -> Interview: ...
def save(interview: Interview, expected_revision: int) -> None: ...
```

`save` must atomically update only where both `interview_id` and `revision` match.
When no row is updated, raise `InterviewConflict`. This preserves the API's `409`
behavior and prevents two patient responses from overwriting each other.

For Round 1, storing `Interview.model_dump(mode="json")` in a JSONB column is enough.
Keep indexed columns for `interview_id`, `patient_id`, `completed`, `revision`, and
timestamps. Validate loaded JSON with `Interview.model_validate(...)` before handing it
back to the engine.

## Patient creation flow

M1 already sends the fixed `Patient` object inside `POST /interview/start`:

```json
{
  "patient": {
    "patient_id": "P1001",
    "name": "Rajesh Kumar",
    "age": 48,
    "gender": "male",
    "language": "hi"
  },
  "consent": true
}
```

When M3 becomes the public API gateway, it should authorize or upsert that patient,
record consent, and start the interview in one application workflow. M1 can then point
`NEXT_PUBLIC_API_BASE_URL` at M3 without changing request or response shapes.

Do not use the interview record as the authoritative demographic record. It carries
`patient_id` and language for interview behavior; the M3 `patients` table owns name,
age, gender, and later demographic corrections.

## Stable M1/M2 endpoints

- `POST /interview/start`
- `POST /interview/respond`
- `POST /interview/complete`
- `GET /interview/{interview_id}`
- `GET /interview/{interview_id}/record`
- `GET /health`

The JSON schemas in `contracts/` are the wire source of truth. The full interview
record is for persistence and downstream M4/M5 evidence; `InterviewResponse` is the
smaller M1 view. M3 should proxy these responses unchanged during initial integration.

## M3 responsibilities before real patient use

- PostgreSQL persistence with atomic revision comparison
- patient and interview ownership checks
- authentication and authorization
- durable consent record and audit fields
- retention/deletion policy
- rate limiting and request tracing without logging patient statements
- restricted CORS origins and TLS at deployment
- migrations keyed by `schema_version`
