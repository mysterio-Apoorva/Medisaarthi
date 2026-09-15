/** Browser API client. All clinical decisions and authorization remain server-side. */
import type {
  BackendInterviewDetailResponse,
  BackendInterviewRespondResponse,
  BackendInterviewStartResponse,
  DoctorEditAuditItem,
  DoctorNarrativeResponse,
  DoctorSummaryEditRequest,
  DoctorSummaryEditResponse,
  DoctorSummaryResponse,
  DoctorSummaryVerifyResponse,
  Language,
  Patient,
  PatientListItem,
} from '@/types';

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || '/api';
export type CareMode = 'MODERN' | 'AYUSH';

export class ApiError extends Error {
  constructor(public readonly status: number, message: string, public readonly data?: unknown) {
    super(message);
    this.name = 'ApiError';
  }
}

type RecordValue = string | number | boolean | string[];
type ClinicalFact = {
  fact_id?: string;
  field_name: string;
  value: RecordValue;
  source: string;
  confidence: number;
  status?: string;
  evidence?: string | null;
  created_at?: string;
};
type NewSummary = {
  patient_snapshot: { patient_id: string; name: string; age: number; gender: string; preferred_language?: string; uhid?: string; phone?: string };
  encounter: { encounter_id: string; status: string; language: Language; stage: string; revision: number; started_at?: string; completed_at?: string; finalized_at?: string; ai_provider: string } | null;
  clinical_state: Record<string, RecordValue>;
  facts: ClinicalFact[];
  completion: { completion_percentage: number; missing: string[]; critical_missing: string[]; contradictions: string[] };
  red_flags: { message: string; severity: string; rule_code: string; evidence: string[] }[];
  narrative: string;
  reconciliation: unknown[];
  documents: unknown[];
  timeline: { event_id: string; occurred_at: string; title: string; detail?: string; source: string; confidence: number; event_type: string }[];
  verification_status: string;
};

function messageFrom(value: unknown, fallback: string): string {
  if (typeof value === 'object' && value !== null && 'detail' in value) {
    const detail = (value as { detail: unknown }).detail;
    if (typeof detail === 'string') return detail;
    if (typeof detail === 'object' && detail !== null && 'message' in detail && typeof (detail as { message: unknown }).message === 'string') return (detail as { message: string }).message;
  }
  return fallback;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: 'include',
      headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...options.headers },
    });
  } catch {
    throw new ApiError(0, 'Unable to reach the MediKiosk service. Confirm that the backend is running.');
  }
  const body: unknown = response.status === 204 ? undefined : await response.json().catch(() => undefined);
  if (!response.ok) throw new ApiError(response.status, messageFrom(body, `Request failed (${response.status})`), body);
  if (response.status !== 204 && body === undefined) throw new ApiError(502, 'The service returned an invalid response. Please retry.');
  return body as T;
}

export type Medicine = { name: string; strength: string; dose: string; frequency: string; duration: string; route: string; instructions: string };
export type Prescription = { revision: number; medicines: Medicine[]; advice: string; no_medicines_reason: string | null; follow_up_at: string | null; doctor_name: string; allergy_review: { allergies: string[] | null; reviewed_by: string; reviewed_at: string } | null };
export type Observation = { observation_id: string; kind: 'VITAL' | 'TEST'; name: string; value: number; unit: string; measured_at: string; source: string; voided_at: string | null; void_reason: string | null };
export type EncounterRecord = { encounter_id: string; status: string; observations: Observation[]; prescription: Prescription | null; pdf_available: boolean; allergies: string[] | null };
export function getEncounterRecord(id: string): Promise<EncounterRecord> { return request(`/records/${encodeURIComponent(id)}`); }
export function saveObservation(id: string, observation: Pick<Observation, 'kind' | 'name' | 'value' | 'unit' | 'measured_at'> & { request_id: string }): Promise<Observation> {
  return request(`/records/${encodeURIComponent(id)}/observations`, { method: 'POST', body: JSON.stringify(observation) });
}
export function voidObservation(id: string, observationId: string, reason: string): Promise<Observation> {
  return request(`/records/${encodeURIComponent(id)}/observations/${encodeURIComponent(observationId)}/void`, { method: 'POST', body: JSON.stringify({ reason }) });
}
export function savePrescription(id: string, prescription: Omit<Prescription, 'revision' | 'doctor_name' | 'allergy_review'> & { expected_revision: number; allergies_reviewed: boolean; allergy_review: string[] | null }): Promise<Prescription> {
  return request(`/records/${encodeURIComponent(id)}/prescription`, { method: 'PUT', body: JSON.stringify(prescription) });
}
export async function downloadRecordPdf(id: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/records/${encodeURIComponent(id)}/pdf`, { credentials: 'include' });
  if (!response.ok) throw new ApiError(response.status, messageFrom(await response.json().catch(() => null), 'PDF generation failed. Please retry.'));
  const blob = await response.blob();
  if (blob.type !== 'application/pdf' || blob.size < 100) throw new Error('The service did not return a valid PDF. Please retry.');
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a'); link.href = url; link.download = `${id}.pdf`; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

export type CurrentUser = { user_id: string; email: string; role: 'PATIENT' | 'DOCTOR' | 'ADMIN'; patient_id?: string | null; display_name: string };

export async function login(email: string, password: string): Promise<CurrentUser> {
  const response = await request<{ user: CurrentUser }>('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) });
  return response.user;
}

export async function logout(): Promise<void> { await request<void>('/auth/logout', { method: 'POST' }); }
export async function getCurrentUser(): Promise<CurrentUser> { return (await request<{ user: CurrentUser }>('/auth/me')).user; }
export async function selectManualIntake(encounterId?: string): Promise<IntakeSnapshot> {
  if (encounterId) {
    await request(`/interviews/${encodeURIComponent(encounterId)}/mode`, { method: 'PATCH', body: JSON.stringify({ processing_mode: 'MANUAL' }) });
    return getIntakeSnapshot(encounterId);
  }
  const result = await request<IntakeSnapshot>('/interviews/start', { method: 'POST', body: JSON.stringify({ patient_id: localStorage.getItem('medisaarthi_current_patient_id'), consent_id: localStorage.getItem('medisaarthi_current_consent_id'), language: localStorage.getItem('medisaarthi_selected_lang') || 'en', care_mode: localStorage.getItem('medisaarthi_care_mode') || 'MODERN', processing_mode: 'MANUAL' }) });
  localStorage.setItem('medisaarthi_current_interview_id', result.encounter_id);
  return result;
}

export async function registerPatient(payload: { name: string; age: number; gender: 'Male' | 'Female' | 'Other'; language: Language; email: string; password: string; phone?: string }): Promise<{ patient_id: string; user: CurrentUser }> {
  return request('/auth/register', { method: 'POST', body: JSON.stringify(payload) });
}

export async function getPatients(): Promise<Patient[]> { return request<Patient[]>('/patients'); }
export async function getPatient(patientId: string): Promise<Patient | null> {
  try { return await request<Patient>(`/patients/${encodeURIComponent(patientId)}`); }
  catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error; }
}

export async function recordConsent(patientId: string, consentType: 'CLINICAL_INTAKE' | 'DOCUMENT_PROCESSING' = 'CLINICAL_INTAKE'): Promise<{ consent_id: string }> {
  return request('/interviews/consents', { method: 'POST', body: JSON.stringify({ patient_id: patientId, consent_type: consentType }) });
}

export async function startInterviewSession(patientId: string, language: Language, consentId?: string, careMode: CareMode = 'MODERN'): Promise<BackendInterviewStartResponse & { revision: number; completion?: unknown }> {
  return request('/interviews/start', { method: 'POST', body: JSON.stringify({ patient_id: patientId, language, consent_id: consentId, care_mode: careMode }) });
}

export type IntakeSnapshot = {
  encounter_id: string; interview_id: string; patient_id: string; language: Language;
  revision: number; status: string; clinical_state: Record<string, RecordValue>;
  completion: { completion_percentage: number; missing: string[]; critical_missing: string[] };
  priority_flags: { code: string; severity: string; message: string }[];
  next_question: { id: string; text: string } | null; ai_warning?: string | null;
  answers: { answer_id: string; question_text: string; answer_text: string; created_at: string }[];
  question_budget: { minimum: number; maximum: number; answered: number; complete: boolean; reason: string | null; unresolved_fields: string[]; needs_clinician_review: boolean };
};
export async function sendIntakeAnswer(id: string, message: string, revision: number, signal?: AbortSignal): Promise<IntakeSnapshot> {
  return request(`/interviews/${encodeURIComponent(id)}/answers`, { method: 'POST', body: JSON.stringify({ message, expected_revision: revision }), signal });
}
export async function getIntakeSnapshot(id: string): Promise<IntakeSnapshot> {
  return request(`/interviews/${encodeURIComponent(id)}`);
}
export async function transcribeInterviewAudio(id: string, audio: Blob, filename: string, revision: number, signal?: AbortSignal): Promise<{ transcript: string; revision: number }> {
  const form = new FormData();
  form.append('file', audio, filename);
  form.append('expected_revision', String(revision));
  return request(`/interviews/${encodeURIComponent(id)}/transcribe`, { method: 'POST', body: form, signal });
}

export async function respondToInterviewSession(interviewId: string, message: string, expectedRevision?: number): Promise<BackendInterviewRespondResponse & { revision: number; clinical_state?: Record<string, RecordValue>; completion?: { completion_percentage: number }; ai_warning?: string | null }> {
  const response = await request<{ encounter_id: string; status: string; extracted_facts: { field_name: string; value: RecordValue; source: string; confidence: number }[]; current_topic: string; next_question: { text: string; type: string } | null; interview_completed: boolean; revision: number; clinical_state: Record<string, RecordValue>; completion: { completion_percentage: number }; ai_warning?: string | null }>(`/interviews/${encodeURIComponent(interviewId)}/answers`, { method: 'POST', body: JSON.stringify({ message, expected_revision: expectedRevision }) });
  return {
    interview_id: response.encounter_id, status: response.status, received_message: message,
    extracted_facts: response.extracted_facts.map((fact) => ({ field_name: fact.field_name, value: String(fact.value), status: fact.source })),
    current_topic: response.current_topic,
    next_question: response.next_question || { text: 'Your intake is ready for review.', type: 'text' },
    interview_completed: response.interview_completed, revision: response.revision, clinical_state: response.clinical_state, completion: response.completion, ai_warning: response.ai_warning,
  };
}

export async function completeInterviewSession(interviewId: string, expectedRevision?: number, reviewed = false): Promise<{ interview_id: string; status: string }> {
  const response = await request<{ encounter_id: string; status: string }>(`/interviews/${encodeURIComponent(interviewId)}/submit`, { method: 'POST', body: JSON.stringify({ expected_revision: expectedRevision, reviewed }) });
  return { interview_id: response.encounter_id, status: response.status };
}

export async function correctPatientFact(id: string, field: string, value: RecordValue, revision: number): Promise<void> {
  await request(`/interviews/${encodeURIComponent(id)}/corrections`, { method: 'POST', body: JSON.stringify({ field_name: field, value, expected_revision: revision }) });
}

export type DocumentUploadResult = {
  document_id: string;
  processing_status: 'PROCESSED' | 'NEEDS_REVIEW' | 'FAILED';
  classification: string | null;
  extracted_count: number;
  confidence: number;
  error_code?: string | null;
};

export type EncounterDocument = {
  document_id: string;
  can_retry: boolean;
  can_remove: boolean;
  original_name: string;
  processing_status: 'PROCESSED' | 'NEEDS_REVIEW' | 'FAILED';
  classification?: string | null;
  classification_confidence?: number | null;
  document_date?: string | null;
  entity_count?: number;
  error_code?: string | null;
  processing_detail_json?: string | null;
};
export type DocumentExtraction = {
  document_id: string;
  status: string;
  error_code?: string | null;
  classification?: string | null;
  classification_confidence?: number | null;
  document_date?: string | null;
  processing_steps: string[];
  text?: string | null;
  facts: { field_name: string; value: string[]; evidence: string; page_numbers?: number[] }[];
  pages: { page_number: number; raw_text: string; extraction_method: string; confidence: number }[];
  entities: { entity_id: string; entity_type: string; field_name?: string | null; value: string; evidence: string; page_number: number; confidence: number; verification_status: string; abnormal_status?: 'LOW' | 'HIGH' | 'NORMAL' | null }[];
  review?: { summary: string; abnormal_results: string[]; requires_physician_verification: string[] };
  match_results?: { field_name: string; status: 'CONSISTENT' | 'NEW_CANDIDATE' | 'CONFLICT_REQUIRES_REVIEW'; page_numbers: number[] }[];
  requires_clinician_review: boolean;
};

export async function uploadEncounterDocument(interviewId: string, file: File): Promise<DocumentUploadResult> {
  const form = new FormData();
  form.append('file', file, file.name);
  return request<DocumentUploadResult>(`/documents/encounters/${encodeURIComponent(interviewId)}`, { method: 'POST', body: form });
}
export async function listEncounterDocuments(interviewId: string): Promise<EncounterDocument[]> {
  return request(`/documents/encounters/${encodeURIComponent(interviewId)}`);
}
export async function getDocumentExtraction(documentId: string): Promise<DocumentExtraction> {
  return request(`/documents/${encodeURIComponent(documentId)}/extraction`);
}
export async function retryDocumentProcessing(documentId: string): Promise<Pick<DocumentUploadResult, 'document_id' | 'processing_status' | 'error_code'> & {entity_count: number; processing_steps: string[]}> {
  return request(`/documents/${encodeURIComponent(documentId)}/retry`, { method: 'POST' });
}
export async function deleteEncounterDocument(documentId: string): Promise<void> {
  await request<void>(`/documents/${encodeURIComponent(documentId)}`, { method: 'DELETE' });
}

export async function sendVoiceInterviewAudio(interviewId: string, audio: Blob, filename = 'recording.webm', expectedRevision?: number): Promise<BackendInterviewRespondResponse & { transcript: string; revision: number; ai_warning?: string | null }> {
  if (!audio.size) throw new ApiError(422, 'The microphone recording is empty. Please record your answer again.');
  const form = new FormData();
  form.append('file', audio, filename);
  if (expectedRevision !== undefined) form.append('expected_revision', String(expectedRevision));
  const response = await request<{ encounter_id: string; status: string; extracted_facts: { field_name: string; value: RecordValue; source: string; confidence: number }[]; current_topic: string; next_question: { text: string; type: string } | null; interview_completed: boolean; revision: number; transcript: string; ai_warning?: string | null }>(`/interviews/${encodeURIComponent(interviewId)}/voice`, { method: 'POST', body: form });
  return {
    interview_id: response.encounter_id,
    status: response.status,
    received_message: response.transcript,
    transcript: response.transcript,
    extracted_facts: response.extracted_facts.map((fact) => ({ field_name: fact.field_name, value: String(fact.value), status: fact.source })),
    current_topic: response.current_topic,
    next_question: response.next_question || { text: 'Your intake is ready for review.', type: 'text' },
    interview_completed: response.interview_completed,
    revision: response.revision,
    ai_warning: response.ai_warning,
  };
}

export async function getInterviewDetail(interviewId: string): Promise<BackendInterviewDetailResponse> {
  const response = await request<{ encounter_id: string; patient_id: string; status: string; encounter: { language: Language; stage: string; started_at?: string; completed_at?: string }; answers: { answer_id: string; question_text: string; answer_text: string; created_at: string }[] }>(`/interviews/${encodeURIComponent(interviewId)}`);
  return { interview_id: response.encounter_id, patient_id: response.patient_id, status: response.status, language: response.encounter.language, current_topic: response.encounter.stage, started_at: response.encounter.started_at, completed_at: response.encounter.completed_at, messages: response.answers.flatMap((answer, index) => [{ id: index * 2 + 1, interview_id: response.encounter_id, role: 'assistant', text: answer.question_text, language: response.encounter.language, timestamp: answer.created_at }, { id: index * 2 + 2, interview_id: response.encounter_id, role: 'patient', text: answer.answer_text, language: response.encounter.language, timestamp: answer.created_at }]) };
}

export async function getDoctorPatients(): Promise<PatientListItem[]> {
  const rows = await request<Array<PatientListItem & { priority: string }>>('/doctor/patients');
  return rows.map((row) => ({ ...row, priority: row.priority === 'EMERGENCY' || row.priority === 'HIGH' ? 'Urgent' : row.priority === 'MODERATE' ? 'Priority' : 'Normal', status: row.status === 'SUBMITTED' ? 'Ready for review' : row.status === 'FINALIZED' ? 'Verified' : row.status }));
}

function summaryAdapter(summary: NewSummary): DoctorSummaryResponse {
  const state = summary.clinical_state;
  const list = (field: string): string[] => Array.isArray(state[field]) ? state[field] as string[] : [];
  const value = (field: string): string | undefined => state[field] === undefined ? undefined : String(state[field]);
  const provenance = (field: string) => summary.facts.find(fact => fact.field_name === field);
  return {
    record_revision: summary.encounter?.revision,
    patient_snapshot: { ...summary.patient_snapshot, preferred_language: summary.patient_snapshot.preferred_language, registration_time: undefined },
    current_complaint: { chief_complaint: value('chief_complaint'), duration: value('duration'), severity: value('severity'), location: value('location'), trigger: value('exertion'), associated_symptoms: Object.entries(state).filter(([field, item]) => ['breathlessness', 'sweating', 'nausea', 'vomiting', 'cough', 'fever'].includes(field) && item === true).map(([field]) => field.replace('_', ' ')).join(', '), facts: summary.facts.map((fact) => ({ field_name: fact.field_name, value: String(fact.value), status: fact.status || 'reported', source: fact.source, confidence: fact.confidence })) },
    past_medical_history: list('past_medical_history').map((condition) => ({ condition, source: provenance('past_medical_history')?.source, confidence: provenance('past_medical_history')?.confidence })),
    medications: list('medications').map((name) => ({ name, source: provenance('medications')?.source })),
    allergies: list('allergies').map((allergen) => ({ allergen, source: provenance('allergies')?.source })),
    allergy_status: state.allergies !== undefined && list('allergies').length === 0 ? 'No known allergies reported' : state.allergies === undefined ? 'No allergy information recorded' : 'Allergy information reported',
    important_findings: summary.red_flags.map((flag) => ({ finding: flag.rule_code, value: flag.message, category: 'Safety rule', status: flag.severity })),
    missing_information: summary.completion.missing.map((field) => ({ field_name: field, description: field.replaceAll('_', ' '), importance: summary.completion.critical_missing.includes(field) ? 'critical' : 'standard' })),
    priority_flags: summary.red_flags.map((flag) => flag.message),
    interview_metadata: { interview_id: summary.encounter?.encounter_id, status: summary.encounter?.status || 'NO_ENCOUNTER', language: summary.encounter?.language, started_at: summary.encounter?.started_at, completed_at: summary.encounter?.completed_at, current_topic: summary.encounter?.stage },
    verification_status: summary.verification_status,
  };
}

async function rawDoctorSummary(patientId: string): Promise<NewSummary> { return request<NewSummary>(`/doctor/patients/${encodeURIComponent(patientId)}/summary`); }
export async function getDoctorSummary(patientId: string): Promise<DoctorSummaryResponse | null> { try { return summaryAdapter(await rawDoctorSummary(patientId)); } catch (error) { if (error instanceof ApiError && error.status === 404) return null; throw error; } }
export async function getDoctorNarrative(patientId: string): Promise<DoctorNarrativeResponse | null> {
  const summary = await rawDoctorSummary(patientId);
  const recordedList = (field: string) => {
    const value = summary.clinical_state[field];
    return Array.isArray(value) ? value.map(String).join(', ') || 'None reported' : 'Not recorded';
  };
  return {
    patient_id: patientId,
    patient_snapshot: `${summary.patient_snapshot.name}, ${summary.patient_snapshot.age} years`,
    presenting_complaint: String(summary.clinical_state.chief_complaint || 'Not recorded'),
    interview_summary: summary.narrative,
    relevant_history: recordedList('past_medical_history'),
    medications: recordedList('medications'),
    allergies: recordedList('allergies'),
    important_findings: summary.red_flags.map((flag) => flag.message).join(' ') || 'No active deterministic safety rule',
    missing_information: summary.completion.missing.join(', ') || 'No required fields missing',
    priority_flags: summary.red_flags.map((flag) => flag.message).join(' ') || 'None',
    verification_note: summary.verification_status,
  };
}

export async function updateDoctorSummary(patientId: string, changes: DoctorSummaryEditRequest): Promise<DoctorSummaryEditResponse> {
  const normalized: Array<[string, RecordValue]> = [];
  if (changes.chief_complaint !== undefined) normalized.push(['chief_complaint', changes.chief_complaint]);
  if (changes.duration !== undefined) normalized.push(['duration', changes.duration]);
  if (changes.severity !== undefined) normalized.push(['severity', changes.severity]);
  if (changes.location !== undefined) normalized.push(['location', changes.location]);
  if (changes.trigger !== undefined) normalized.push(['exertion', changes.trigger]);
  if (changes.past_medical_history !== undefined) normalized.push(['past_medical_history', changes.past_medical_history.map((item) => item.condition).filter(Boolean)]);
  if (changes.medications !== undefined) normalized.push(['medications', changes.medications.map((item) => [item.name, item.dosage, item.frequency].filter(Boolean).join(' — ')).filter(Boolean)]);
  if (changes.allergies !== undefined) normalized.push(['allergies', changes.allergies.map((item) => [item.allergen, item.reaction].filter(Boolean).join(' — ')).filter(Boolean)]);
  const auditEntries: DoctorEditAuditItem[] = [];
  for (const [fieldName, value] of normalized) {
    const response = await request<{ fact_id: string; field_name: string; previous_value: RecordValue | null; value: RecordValue }>(`/doctor/patients/${encodeURIComponent(patientId)}/facts`, { method: 'POST', body: JSON.stringify({ field_name: fieldName, value, reason: 'Clinician correction from dashboard' }) });
    auditEntries.push({ audit_id: response.fact_id, patient_id: patientId, field_name: response.field_name, original_value: response.previous_value === null ? null : String(response.previous_value), corrected_value: String(response.value), changed_by: 'Authenticated clinician', changed_at: new Date().toISOString() });
  }
  return { patient_id: patientId, updated_fields: auditEntries.map((entry) => entry.field_name), verification_status: 'DOCTOR_REVIEW_REQUIRED', audit_entries: auditEntries };
}

export async function verifyDoctorSummary(patientId: string, followUp?: { treatmentPlan?: string; followUpAt?: string }): Promise<DoctorSummaryVerifyResponse> {
  const summary = await rawDoctorSummary(patientId);
  if (!summary.encounter) throw new ApiError(409, 'No encounter is available to finalize.');
  const response = await request<{ finalized_by: string; finalized_at: string }>(`/doctor/encounters/${encodeURIComponent(summary.encounter.encounter_id)}/finalize`, { method: 'POST', body: JSON.stringify({ treatment_plan: followUp?.treatmentPlan || null, follow_up_at: followUp?.followUpAt || null }) });
  return { patient_id: patientId, verification_status: 'FINALIZED', verified_by: response.finalized_by, verified_at: response.finalized_at };
}

export async function getDoctorAudit(patientId: string): Promise<DoctorEditAuditItem[]> {
  const rows = await request<Array<{ audit_id: string; resource_id: string; action: string; metadata: { field?: string; from?: RecordValue | null; to?: RecordValue }; created_at: string; actor_user_id?: string }>>(`/doctor/patients/${encodeURIComponent(patientId)}/audit`);
  return rows.filter((row) => row.action === 'DOCTOR_CORRECTED_FACT').map((row) => ({ audit_id: row.audit_id, patient_id: patientId, field_name: row.metadata.field || 'clinical_fact', original_value: row.metadata.from === null || row.metadata.from === undefined ? null : String(row.metadata.from), corrected_value: row.metadata.to === undefined ? null : String(row.metadata.to), changed_by: row.actor_user_id || 'Authenticated clinician', changed_at: row.created_at }));
}

export type FollowUpQuestion = { id: string; text: string };
export type FollowUpAlert = { follow_up_alert_id: string; severity: 'MODERATE' | 'HIGH' | 'EMERGENCY'; message: string; status: 'OPEN' | 'ACKNOWLEDGED' | 'RESOLVED'; created_at: string; evidence?: string[] };
export type FollowUpSession = { follow_up_session_id: string; follow_up_plan_id: string; patient_id: string; status: 'ACTIVE' | 'COMPLETED'; revision: number; risk_level: 'LOW' | 'MODERATE' | 'HIGH' | 'EMERGENCY'; started_at: string; completed_at?: string | null };
export type FollowUpCheckIn = {
  plan: { follow_up_plan_id: string; patient_id: string; encounter_id: string; instructions?: string | null; follow_up_at?: string | null; status: string; created_at: string };
  session: FollowUpSession;
  record_context: { language: Language; chief_complaint?: string; medications: string[]; allergies: string[]; doctor_instructions: string };
  responses: { follow_up_response_id: string; question_id: string; question_text: string; response_text: string; source: string; created_at: string }[];
  next_question: FollowUpQuestion | null;
  alerts: FollowUpAlert[];
  resumed?: boolean;
  ai_warning?: string;
};
export type FollowUpPlanOverview = { plan: FollowUpCheckIn['plan']; sessions: FollowUpSession[]; alerts: FollowUpAlert[]; last_check_in: FollowUpSession | null };
export async function getPatientFollowUps(patientId: string): Promise<FollowUpPlanOverview[]> {
  return request(`/follow-ups/patients/${encodeURIComponent(patientId)}`);
}
export async function startFollowUpCheckIn(planId: string): Promise<FollowUpCheckIn> {
  return request(`/follow-ups/plans/${encodeURIComponent(planId)}/sessions`, { method: 'POST' });
}
export async function answerFollowUp(sessionId: string, questionId: string, message: string, expectedRevision: number): Promise<FollowUpCheckIn> {
  return request(`/follow-ups/sessions/${encodeURIComponent(sessionId)}/answers`, { method: 'POST', body: JSON.stringify({ question_id: questionId, message, expected_revision: expectedRevision }) });
}
export async function transcribeFollowUpAudio(sessionId: string, audio: Blob, filename: string, revision: number): Promise<{ transcript: string; revision: number }> {
  const form = new FormData();
  form.append('file', audio, filename);
  form.append('expected_revision', String(revision));
  return request(`/follow-ups/sessions/${encodeURIComponent(sessionId)}/transcribe`, { method: 'POST', body: form });
}
export async function acknowledgeFollowUpAlert(alertId: string): Promise<{ follow_up_alert_id: string; status: string }> {
  return request(`/follow-ups/alerts/${encodeURIComponent(alertId)}/acknowledge`, { method: 'POST' });
}
export type AdminUser = { user_id: string; email: string; role: 'PATIENT' | 'DOCTOR' | 'ADMIN'; display_name: string; patient_id?: string | null; created_at: string };
export type AdminAudit = { audit_id: string; action: string; resource_type: string; resource_id: string; actor_user_id?: string | null; created_at: string; metadata: Record<string, unknown> };
export type AdminOntology = { built_in: Record<string, unknown>; custom: Array<{ rule_id: string; concept: string; payload: Record<string, unknown>; enabled: number | boolean; updated_at: string }> };

export async function getAdminUsers(): Promise<AdminUser[]> { return request<AdminUser[]>('/admin/users'); }
export async function updateAdminUserRole(userId: string, role: AdminUser['role']): Promise<{ user_id: string; role: AdminUser['role'] }> {
  return request(`/admin/users/${encodeURIComponent(userId)}/role`, { method: 'PUT', body: JSON.stringify({ role }) });
}
export async function getAdminAudits(): Promise<AdminAudit[]> { return request<AdminAudit[]>('/admin/audit-logs'); }
export async function getAdminOntology(): Promise<AdminOntology> { return request<AdminOntology>('/admin/ontology'); }
export async function saveAdminOntologyRule(ruleId: string, payload: { concept: string; payload: Record<string, unknown>; enabled: boolean }): Promise<{ rule_id: string; concept: string; enabled: boolean }> {
  return request(`/admin/ontology/${encodeURIComponent(ruleId)}`, { method: 'PUT', body: JSON.stringify(payload) });
}
export async function getDashboardStats() { const patients = await getDoctorPatients(); return { patientsWaiting: patients.length, interviewsCompleted: patients.filter((patient) => patient.status === 'Ready for review' || patient.status === 'Verified').length, needsReview: patients.filter((patient) => patient.status === 'Ready for review').length, priorityReviews: patients.filter((patient) => patient.priority !== 'Normal').length }; }
