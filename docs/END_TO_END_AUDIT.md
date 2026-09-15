# End-to-end implementation and acceptance evidence

Test date: 2026-09-15. This report concerns the local MediKiosk workflow, not certification for clinical deployment or an assertion that software has zero possible bugs.

## Shutdown recovery verification

See [the audit and status map](RESUME_AUDIT.md). The existing workflow passed before edits and again after targeted completion work. The latest suite has **183 passing tests**, and the regenerated inventory has successful execution evidence for **59 endpoints**. The fresh browser run uses `.runtime/resume-acceptance.sqlite3`, with a distinct synthetic patient and no changes to pre-existing patient records.

The second complete browser run includes systolic/diastolic blood pressure, pulse, temperature, SpO2, height, weight, a source-linked calculated BMI, and a laboratory result. It checks separate medicine strength/instructions, doctor allergy review, persisted prescription, finalization, all four A4 PDF pages, and follow-up response/alert/timeline delivery. API process restart checks confirm that finalized records, all nine observations, prescription fields, follow-up events and PDF generation survive restart.

The bug hunt found and repaired a clipped multipage PDF: MuPDF 1.28's 10pt base layout could report completion with later paragraphs outside the page. The renderer now uses its native 12pt base, rejects overflowing layouts, and bounds pagination. A 30-medicine regression verifies every instruction marker and the later advice section across pages. Existing finalized snapshots still render after migration 9; absent legacy prescription fields stay visibly unrecorded.

Additional regression coverage includes stale allergy reviews at saving/finalization, required strength/instructions, vital-unit mismatch, duplicate observations, BMI source withdrawal/recalculation, retained document vital units and decimal heights, reconciliation timeline/audit visibility, and rejected unsaved treatment advice at finalization. No extra endpoint family, timeline or prescribing model was introduced.

After the final document-action fix, the full browser flow passed once more with no browser errors. The original database was backed up, migrated and restored as the running API's data source with seeding disabled. A row-by-row comparison verifies unchanged original values in all 28 pre-existing data tables; SQLite integrity and foreign-key checks pass. The detailed running-state and evidence paths are in the recovery audit.

## Data and execution boundaries

- SQLite is authoritative for identity, consent, answers, facts, documents/entities/pages, measurements, prescription, finalization, follow-up and audit. Browser refresh tests retrieve those records from the API.
- Normal startup does not seed clinical data. Synthetic fixtures are in `backend/demo_data.py`, tests and acceptance scripts only.
- Question wording and extraction call local Ollama. Provider failure does not silently switch to rules. Explicit manual intake is visibly identified and uses the same server budget and persistence.
- Microphone PCM passes through AudioWorklet capture, VAD and actual faster-whisper. Piper generates the question audio; the SVG avatar mouth follows audio amplitude. Acceptance audio is synthetic speech replacing the physical microphone source only.
- Real PDF text extraction and image OCR produce retained, page-backed evidence. Document classification/entity recognizers are conservative source-text processing, not an unrestricted medical AI. Unrecognized material remains available in the original and extracted page text.
- A4 PDFs are rendered and reopened from the immutable finalized database snapshot, including stored prescriptions. No screen capture is used to create the medical PDF.
- Follow-up questions use finalized encounter and prescription context; responses and alerts persist and update the clinician timeline. Alert rules do not independently diagnose or change treatment.

## Completed checks

| Gate | Evidence |
|---|---|
| Production Next build and TypeScript | `npm run build` passed; all application routes generated |
| Strict lint | `npm run lint -- --max-warnings 0` passed; migration-rule downgrades removed |
| Backend type check | mypy passed for 28 application source files |
| Backend unit/API/DB integration | Complete pytest suite; latest counts in `.runtime/api-test-coverage.json` and test output |
| Client contract regression checks | 12 passing source-contract checks; these supplement, not replace, browser tests |
| VAD/capture | Pauses, silence, short/long speech and noise checks passed; 104-second PCM recording retained without reordering |
| Actual local AI/OCR | `local_ai_checks.py` passed OCR, embeddings, exact-source model excerpts, summary, integrated voice persistence, follow-up ASR and TTS |
| Full fresh-patient browser flow | `.runtime/full-e2e/result.json`; fresh registration, consent, five adaptive voice questions, source review, multiple documents, vitals/tests, assignment, doctor review, prescription, finalization, PDF, follow-up and acknowledgement |
| Ten-question cap | `backend/data/handsfree-e2e/limit.json`: ten real transcriptions, complete budget, no next question |
| Microphone denied | `backend/data/handsfree-e2e/permission.json`: visible recoverable microphone error, no fabricated transcript |
| Endpoint inventory | `API_AUDIT.md`: all 59 method/path contracts have actual successful execution evidence; protected routes also have authentication/outage checks |

The PDF acceptance test reopens the downloaded file, checks A4 dimensions and verifies patient identity, corrected history, source findings, measurements, every prescription instruction, advice and follow-up date. It renders a page to `.runtime/full-e2e/opened-pdf-page.png`. NFKC normalization is used only for the test's extracted-text comparison because PDF fonts may produce ligatures.

## Failure and consistency checks

Automated tests cover missing/malformed fields, invalid file signatures and oversized documents, duplicate upload, inaccessible resources, unassigned clinicians, patient calls to staff APIs, expired sessions, disallowed origins, stale revisions, empty answers, capped interviews, unavailable model/ASR/TTS/embeddings/database/PDF, OCR failure with retained source and retry, measurement validation and withdrawal, concurrent prescription writes, transaction rollback, foreign keys and immutable finalized snapshots. Deliberate outage injection occurs only in tests; no core service returns fabricated successful results.

The final browser runner additionally disconnects the browser before saving a patient correction, verifies a visible network error and retained draft, reconnects, and retries the real request. No patient answer is fabricated to recover from that failure.

Changes made during the bug hunt include eliminating silent AI fallback, moving inference outside database write locks, preserving drafts against late load responses, revision updates for documents/measurements, serialized clinician mutations, document duplicate detection and lifecycle locks, removing false processing progress, connecting prescription/PDF/follow-up, removing unused mock/legacy modules and default sign-in credentials, and correcting lab reference-range parsing.

## Reproduce against isolated servers

Use separate terminals. Set these values only for the acceptance API process:

```powershell
$env:DATABASE_URL='sqlite:///.runtime/acceptance.sqlite3'
$env:DOCUMENT_UPLOAD_DIR='.runtime/acceptance-uploads'
$env:SEED_DEMO_DATA='true'
$env:AI_PROVIDER='ollama'
& backend/.venv/Scripts/python.exe -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Run `npm run dev` in another terminal, with the local Ollama and downloaded speech models available. Then run `npm run test:complete`. The application user flow is browser-driven, including registration, assignment, prescription entry and follow-up. The synthetic account names and test medicine are clearly identified as software test inputs.

Run `npm run test:unit`, `npm run test:local-ai`, then `backend/scripts/audit_endpoints.py` to refresh the endpoint evidence. Do not edit Python application files during a live browser run if uvicorn is running with `--reload`; a reload deliberately restarts in-flight services.

## Evidence limitations

Status coverage and observed JSON shapes do not prove every possible input/failure combination. Browser tests do not certify physical microphone/speaker hardware, production access controls outside this application, clinical validity, hospital integration or medical-device integration. Existing 2026-09-13 reports are historical and are superseded by this report for the current workflow.
