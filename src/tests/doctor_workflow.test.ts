import { describe, test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const read = (relativePath: string) =>
  fs.readFileSync(path.resolve(process.cwd(), relativePath), 'utf-8');

describe('Doctor client contract', () => {
  test('renders an API-backed doctor workspace and patient review route', () => {
    const dashboard = read('src/app/doctor/page.tsx');
    const list = read('src/components/doctor/PatientList.tsx');
    assert.match(dashboard, /getDoctorPatients/);
    assert.match(list, /\/doctor\/patients/);
    assert.match(list, /Review Patient/);
  });

  test('uses session-backed doctor APIs, not caller-supplied role headers', () => {
    const api = read('src/services/api.ts');
    assert.match(api, /\/doctor\/patients/);
    assert.match(api, /\/doctor\/encounters/);
    assert.match(api, /credentials: 'include'/);
    assert.doesNotMatch(api, /X-Doctor-ID/);
    assert.doesNotMatch(api, /doctor_demo/);
  });

  test('keeps clinician correction and verification actions connected to API methods', () => {
    const api = read('src/services/api.ts');
    assert.match(api, /updateDoctorSummary/);
    assert.match(api, /verifyDoctorSummary/);
    assert.match(api, /DOCTOR_REVIEW_REQUIRED/);
    assert.match(api, /\/facts/);
    assert.match(api, /\/finalize/);
  });

  test('presents provenance and verification status in the patient review UI', () => {
    const profile = read('src/components/doctor/PatientProfileHeader.tsx');
    const facts = read('src/components/doctor/StructuredClinicalData.tsx');
    assert.match(profile, /AI-assisted \/ unverified/);
    assert.match(profile, /Verified/);
    assert.match(facts, /source|provenance/i);
  });
});
