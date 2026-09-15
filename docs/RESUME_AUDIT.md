# Shutdown recovery audit — 2026-09-15

## Baseline inspected before application edits

HEAD: `d2f74ef` (2026-09-15 02:21 +0530). The worktree already contained 88 tracked changes plus new records/PDF modules, clinical-record UI, tests and acceptance reports. These changes were preserved, including removal of obsolete mock/duplicate modules. No reset, checkout, reinstall or database replacement was performed.

Inspected source inventory, routes/clients, eight additive SQLite migrations, dependency manifests, configuration keys (without exposing credentials), AI/document/audio services, tests, recent logs and saved acceptance evidence. Existing local `.env` contains older provider settings; active services use local Ollama defaults. `pip check` passes and npm dependencies resolve. Both existing and isolated SQLite databases pass integrity checks and have migrations 1–8. The existing patient database was inspected read-only; new workflow checks use `.runtime/resume-acceptance.sqlite3` and `.runtime/resume-uploads` with explicit synthetic seeds.

Fresh baseline verification: 167 backend tests pass; strict lint passes; production Next.js build passes with all routes. Next.js bundled installation guidance was read. Frontend and backend start and respond successfully. The browser acceptance rerun uses actual models and generated spoken WAVs as the microphone source. Physical microphone/speaker acceptance remains an on-site check.

## Implementation status before fixes

COMPLETE means the named automated behavior has execution evidence, not clinical certification or proof against all possible inputs. PARTIAL includes implemented features awaiting the fresh browser rerun.

| Feature | Baseline status | Evidence | Action |
|---|---|---|---|
| AI interview and adaptive questions | PARTIAL (live recheck) | interviews.py, ai/questions.py, orchestrator.py; unit tests; saved browser run | Run fresh local model workflow; preserve |
| Full-screen avatar, speaking/listening/thinking | PARTIAL (live recheck) | TalkingAvatar.tsx, interview/page.tsx, useAssistantSpeech.ts | Verify animation and state transitions; preserve |
| Automatic listening, VAD, end of speech, interruption | PARTIAL (live recheck) | voice-activity.ts; browser_handsfree_e2e.py | Run capture/failure/cap scenarios; preserve |
| Real STT and TTS | PARTIAL (live recheck) | faster-whisper voice.py, Piper tts.py; local voices/models installed | Recheck actual inference sequentially |
| 5–10 questions, no question 11 | COMPLETE (API/database tests) | question_budget.py, migration 8 trigger, test_question_budget.py | Preserve; repeat real ten-answer browser scenario |
| Multiple documents, storage, PDF/image extraction, OCR | PARTIAL (live recheck) | document_processing.py, documents.py, DocumentReview.tsx | Verify actual PDF/image OCR, refresh and failures |
| Classification, entities, confidence, provenance, duplicates | COMPLETE (integration tests) | document pages/entities/extractions; document tests | Preserve; verify live source values |
| Document/interview matching and reconciliation | PARTIAL | persisted candidates and decisions work; timeline source labels can remain stale | Synchronize decision status into existing timeline |
| Unified timeline | PARTIAL | one timeline_events table combines all requested sources | Extend review status; preserve architecture |
| Vitals, laboratory tests, manual entry | PARTIAL | observations table/API/UI persists arbitrary readings | Add named unit validation and height/weight-derived BMI; duplicate-value check |
| Doctor dashboard and editing | PARTIAL (live recheck) | existing chart, source review, measurements and timeline consumers | Preserve; verify fresh assignment/review |
| Prescription/advice/remedies | PARTIAL | persisted revisioned plan and clinician finalization | Add separate strength/instructions and recorded allergy review |
| A4 multipage PDF | PARTIAL | actual snapshot-backed PyMuPDF rendering and integration tests | Include added fields and prove multipage output |
| Follow-up agent/alerts | PARTIAL (live recheck) | persisted plans/questions/responses/alerts; timeline tests | Preserve; include complete medicine instructions in context |
| AYUSH | COMPLETE (integration tests) | care_mode, AYUSH fields/questions, source/timeline/dashboard tests | Preserve and rerun tests |
| Authentication/authorization | COMPLETE (integration tests) | server session, ownership and assigned clinician checks; all protected endpoints | Preserve; exercise login in browser |
| Audit logging | PARTIAL | stored logs exist; reconciliation entries omitted from patient audit filter | Repair patient-scoped reconciliation audit visibility |
| Endpoint inventory | COMPLETE (inventory; live inference recheck) | 59 mounted method/path contracts, API_AUDIT.md, endpoint tests | Regenerate after final execution evidence |
| Error handling | COMPLETE (covered API failure cases) | unavailable AI/STT/TTS/OCR/DB/PDF, corrupt uploads, stale writes, RBAC tests | Extend regressions for discovered gaps |

## Priorities

- **P0:** Repair stale reconciliation timeline status and missing patient-scoped reconciliation audit entries.
- **P1:** Finish prescription fields/allergy review, vital unit validation, persisted BMI with source links and duplicate measurement protection.
- **P2:** No missing subsystem requires a second architecture, model, endpoint family or timeline.
- **P3:** Preserve visual style; only add controls needed for the completed data contracts.

BMI arithmetic uses kilograms divided by height in metres squared, without diagnostic categories: [CDC calculation reference](https://www.cdc.gov/growth-chart-training/hcp/using-bmi/calculating-bmi.html).

## Verified fixes and acceptance

- Preserved the existing interview, avatar, question budget, OCR engines, unified timeline, dashboards and authentication architecture. No dependencies, model installations or endpoint families were added.
- Added migration 9 for prescription allergy-review evidence and observation calculation metadata. Strength and per-medicine instructions use the existing prescription JSON. Old finalized snapshots remain unchanged and still generate PDFs.
- Completed named vital unit validation, duplicate measurement rejection, persistent BMI and source withdrawal/recalculation. The UI exposes the existing measurement API; it does not create a second vital model.
- Recorded reconciliation decisions in the existing timeline, updated source verification labels and included reconciliation IDs in the patient audit query.
- Fixed PDF clipping exposed by the 30-medicine multipage regression. Every instruction and the later advice section must be present; overflowing output fails explicitly. Pagination is bounded.
- Removed unavailable Retry/Remove actions using server-supplied document capabilities. Reviewed documents are rejected before OCR work begins, with another lifecycle check before persistence.
- Reject unsaved advice passed to the legacy finalization body; the saved prescription remains the authoritative plan.

| Acceptance gate | Result and evidence |
|---|---|
| Baseline workflow before edits | PASS, `.runtime/resume-baseline-result.json` |
| Fresh workflow with completed fields | PASS, `.runtime/full-e2e/result.json`; five real transcribed answers, actual Piper speech/avatar motion, PDF and image OCR, document review/reconciliation, every named vital, BMI, test, doctor review, complete prescription, finalization, four-page A4 PDF, follow-up and doctor alert |
| Backend unit/API/database/failure suite | 183 passing tests; two upstream test-client deprecation warnings, no test failures |
| Endpoint audit | 59 method/path contracts with successful execution evidence; all protected endpoints checked for missing authentication and database outage; regenerated `API_AUDIT.md` and JSON contracts |
| Production frontend/build | PASS, all routes generated with TypeScript checks |
| Lint and backend typing | Strict lint passes; mypy passes for all 28 application modules |
| Client regression and VAD | 12 client contract checks pass; pause/noise/silence/long-speech checks and 104-second capture retention pass |
| Actual local services | `local_ai_checks.py` passes image OCR, embeddings, grounded summary, actual follow-up ASR, integrated voice-answer persistence and authenticated TTS |
| Ten-question boundary | `backend/data/handsfree-e2e/limit.json`: ten actual transcriptions, completed budget, no next question; unresolved fields remain flagged |
| Microphone denied | `backend/data/handsfree-e2e/permission.json`: recoverable microphone error, no fabricated response |
| Process-restart persistence | Fresh authenticated requests after API restart retrieve finalized status, all nine observations, prescription fields, follow-up timeline and generated PDF |
| Database integrity | SQLite integrity passes and zero foreign-key violations after migration 9; original database backup is `.runtime/pre-resume-migration.sqlite3` |
| Source audit | No TODO/FIXME/MOCK/DUMMY/FAKE/PLACEHOLDER/HARDCODED/COMING SOON/console.log matches in `src` or `backend/app`; synthetic values remain in explicit demo/test inputs |

The final automated status of the required software features above is COMPLETE within the exercised acceptance cases. This is not proof of zero possible defects or medical suitability. Real spoken WAVs replace microphone hardware in automation; the physical microphone and speakers still require an on-site check. No hardware/device integration or clinical certification is claimed.

## Running state after acceptance

The final fresh browser rerun also passes after the document-action fix, including the assertion that finalized documents expose no Retry button. Endpoint evidence was regenerated afterward.

The frontend remains at `http://127.0.0.1:3000` and the API at `http://127.0.0.1:8000`. The API now uses the original `backend/data/medikiosk.sqlite3` and `backend/data/uploads`, with `SEED_DEMO_DATA=false`. Both services respond successfully. Migration 9 was applied only after creating the original-database backup.

A row-by-row comparison of every pre-existing column confirms **all original values in 28 tables are unchanged** (excluding the deliberately updated migration ledger). Integrity and foreign-key checks pass. Value-free evidence: `.runtime/preserved-database-evidence.json`. Synthetic acceptance records remain isolated in `.runtime/resume-acceptance.sqlite3`.
