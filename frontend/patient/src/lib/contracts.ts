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
  persistence: "memory" | "external";
}
