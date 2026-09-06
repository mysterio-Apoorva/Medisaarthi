# M3 integration record

The teammate repository at `https://github.com/Aryanuo/SIH` was reviewed and integrated
on 2026-09-06.

## Imported design

Its useful ownership model was retained:

- `patients`
- `interviews`
- `medical_history`
- `medications`
- `allergies`
- patient CRUD and combined history routes

## Reconciliation decisions

The teammate `/interview/*` routes only stored raw questions and answers, while the
existing application already had the canonical adaptive interview engine, structured
clinical state, evidence, revision checks, and patient UI contract. Running both route
sets would have created conflicting APIs and separate interview IDs.

The unified `SQLiteRepository` therefore implements the existing `InterviewStore`
boundary and adds the teammate's longitudinal patient tables. One FastAPI process now
owns patient registration, interviews, history, summary/timeline generation, and doctor
review. The complete validated interview is the persisted source of truth; the current
complaint and symptoms remain projections of `clinical_state`.

The teammate code expected an already-provisioned Supabase project but did not include
SQL migrations or Python dependencies. The integrated MVP uses an idempotent local SQL
schema so a fresh clone runs without another person's cloud credentials. A future
PostgreSQL/Supabase adapter can implement the same repository/store methods without
changing frontend contracts.

## Invariants

- Patient name and age are required in the integrated patient journey.
- Consent is recorded on the durable interview record.
- Interview writes compare `expected_revision` atomically.
- Physician edits compare summary `expected_version` atomically.
- Approval is stored with doctor ID and timestamp.
- Doctor endpoints require a database-backed bearer session.
- No sample patient or medical history is inserted automatically.
- Tests may explicitly inject `MockProvider`; the running app defaults to Gemini.
