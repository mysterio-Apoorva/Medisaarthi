import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const read = (relativePath: string) =>
  fs.readFileSync(path.resolve(process.cwd(), relativePath), 'utf-8');

describe('Patient client contract', () => {
  test('keeps the patient journey and consent screens available', () => {
    assert.match(read('src/app/patient/page.tsx'), /Welcome to Medisaarthi/);
    assert.match(read('src/app/patient/language/page.tsx'), /Language/);
    const consent = read('src/app/patient/consent/page.tsx');
    assert.match(consent, /I Agree & Continue/);
    assert.match(consent, /shared with the doctor for review/);
  });

  test('uses authenticated API calls rather than frontend patient fixtures', () => {
    const api = read('src/services/api.ts');
    assert.match(api, /credentials: 'include'/);
    assert.match(api, /\/auth\/login/);
    assert.match(api, /\/auth\/register/);
    assert.match(api, /\/interviews\/consents/);
    assert.match(api, /\/interviews\/start/);
    assert.match(api, /\/answers/);
    assert.match(api, /\/submit/);
    assert.doesNotMatch(api, /INITIAL_PATIENTS|mock-data/);
  });

  test('carries optimistic revision values through every mutable intake request', () => {
    const api = read('src/services/api.ts');
    assert.match(api, /expected_revision: expectedRevision/);
    assert.match(api, /expected_revision', String\(expectedRevision\)/);
  });

  test('shows recoverable errors and keeps a typed response path', () => {
    const interview = read('src/app/patient/interview/page.tsx');
    assert.match(interview, /errorMessage/);
    assert.match(interview, /Retry/);
    assert.match(interview, /id="patient-answer-input"/);
    assert.doesNotMatch(interview, /console\.error\(err\.stack\)/);
  });
});
