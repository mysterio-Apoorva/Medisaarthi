# MediKiosk integration audit

Baseline: 2026-09-13. Existing Next.js 16 / React 19 / FastAPI / SQLite, session RBAC, local Qwen 2.5 3B, faster-whisper, PDF extraction preserved. Existing worktree changes predate this pass.

Observed in source and headless Edge before implementation:
- Interview has no avatar; browser TTS has no visible lip synchronization.
- Audio submits immediately, preventing correction; voice response fails to update client revision.
- Refresh creates encounters; client defaults to P1001; failed sends clear patient text.
- Progress is a question-count estimate; flags/completeness are dropped in client mapping.
- Transcript adapter expects a nested encounter the API does not return.
- Doctor lacks UI for reconciliation, documents, and longitudinal events exposed by API.
- Severity allows unsafe types; boolean negation regex is incorrectly escaped and numbers in duration can become severity.
- Finalization can bypass patient submission; document upload permits finalized records; some errors leave files behind.
- Admin ontology writes are not used by question selection; FHIR mapping uses invalid encounter status codes.
- No rate limiting or explicit CSRF origin validation; environment variable names differ from documentation.
- Existing tests mostly exercise happy-path APIs or source text, not browser behavior.

Work sequence: clinical validation and lifecycle; speech review and talking avatar; patient/doctor review integration; real agent orchestration and provider monitoring; documents, knowledge retrieval, interoperability; isolated failure tests and browser workflow; documentation and evidence.

Acceptance evidence must distinguish unit test doubles, actual model inference, actual audio processing, browser capture/playback, and external adapters. No real patient data is used in tests. No live ABDM/HIS connection is claimed.

Final verification: 23 backend tests passed; production Next.js build and lint error check passed; actual local OCR/embedding/summary checks passed; real Edge patient-to-doctor-to-admin workflow and registration/assignment authorization passed. The full evidence, fixes, run commands and remaining scope are in [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md). Physical audio hardware and live hospital integrations are not certified by these tests.
