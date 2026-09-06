export type Language = "en" | "hi";
export type Gender = "male" | "female" | "other" | "unknown";

export interface Patient {
  patient_id: string;
  name: string;
  age: number | null;
  gender: Gender;
  language: Language;
}

export interface NextQuestion {
  id: string;
  text: string;
  type: "text";
  language: Language;
  clarification: boolean;
}

export interface Fact {
  field: string;
  value: string | number | boolean | string[] | null;
  status: "reported" | "unknown" | "declined";
  evidence: string;
}

export interface Extraction {
  facts: Fact[];
  uncertain_fields: string[];
}

export interface ClinicalState {
  chief_complaint: string | null;
  hpi: string | null;
  duration: string | null;
  severity: number | null;
  location: string | null;
  temperature: string | null;
  breathlessness: boolean | null;
  breathlessness_onset: string | null;
  cough: boolean | null;
  sudden_onset: boolean | null;
  vomiting: boolean | null;
  past_medical_history: string[] | null;
  medications: string[] | null;
  allergies: string[] | null;
  family_history: string[] | null;
  personal_history: string[] | null;
}

export interface PriorityFlag {
  code: string;
  message: string;
  source: "prototype_rule";
  evidence_fields: string[];
}

export interface InterviewResponse {
  schema_version: "1.0";
  patient_id: string;
  interview_id: string;
  revision: number;
  extracted: Extraction;
  clinical_state: ClinicalState;
  missing_information: string[];
  unknown_information: string[];
  next_question: NextQuestion | null;
  priority_flags: PriorityFlag[];
  completed: boolean;
  completion_reason: "collected" | "patient_requested" | "turn_limit" | null;
}

export interface StartRequest {
  patient: Patient;
  consent: true;
}

export interface RespondRequest {
  interview_id: string;
  response: string;
  expected_revision: number;
}

export interface CompleteRequest {
  interview_id: string;
  expected_revision: number;
}

export interface RuntimeStatus {
  status: "ok";
  schema_version: "1.0";
  extraction_mode: "mock" | "gemini";
  persistence: "memory" | "sqlite";
}

export interface DoctorPatient {
  patient: Patient;
  interview_id: string | null;
  completed: boolean;
  updated_at: string | null;
  chief_complaint: string | null;
  summary_status: "draft" | "approved" | null;
}

export interface EditableClinicalSummary {
  patient_snapshot: Patient & { name: string; age: number };
  current_complaint: { name: string | null; duration: string | null; severity: number | null };
  interview_summary: string;
  past_history: string[];
  medications: string[];
  allergies: string[];
  important_findings: string[];
  missing_information: string[];
  priority_flags: string[];
}

export interface ClinicalSummary extends EditableClinicalSummary {
  interview_id: string;
  patient_id: string;
  status: "draft" | "approved";
  version: number;
  updated_at: string | null;
  approved_at: string | null;
}

export interface TimelineEvent {
  date: string | null;
  title: string;
  detail: string | null;
  source: string;
  confidence: number;
}

export interface AuthStatus { needs_setup: boolean }

export interface AuthToken {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  doctor: { doctor_id: number; username: string; display_name: string };
}
