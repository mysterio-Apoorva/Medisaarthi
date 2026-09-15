export type Gender = 'Male' | 'Female' | 'Other';
export type Language = 'hi' | 'en';
export type PatientStatus = 'Ready for review' | 'Needs review' | 'Verified' | 'In consultation' | 'Completed';
export type PriorityLevel = 'Normal' | 'Priority' | 'Urgent';

export interface Patient {
  patient_id: string;
  name: string;
  age: number;
  gender: Gender;
  language: Language;
  phone?: string;
  uhid?: string;
  registration_time?: string;
}

export interface InterviewMessage {
  id: string;
  sender: 'ai' | 'patient';
  text: string;
  timestamp: string;
  extracted_info?: {
    label: string;
    value: string;
  }[];
}

export interface ExtractedSymptomData {
  chief_complaint: string;
  duration: string;
  severity: string; // e.g., "7/10"
  location?: string;
  associated_symptoms: string[];
  onset?: string;
  triggers?: string;
  previous_episodes?: string;
}

export interface Interview {
  interview_id: string;
  patient_id: string;
  chief_complaint: string;
  symptoms: string[];
  responses: InterviewMessage[];
  completed: boolean;
  extracted_data: ExtractedSymptomData;
  started_at: string;
  completed_at?: string;
}

export interface MedicalCondition {
  id?: string;
  year: string;
  condition: string;
  status: string;
  notes?: string;
}

export interface Medication {
  id?: string;
  name: string;
  dosage: string;
  frequency?: string;
  purpose?: string;
}

export interface TimelineEvent {
  id: string;
  date: string;
  year?: string;
  fact: string;
  source: 'EMR' | 'Patient Interview' | 'Clinical Record' | 'Prescription';
  confidence: 'High' | 'Medium' | 'Low';
  category?: 'condition' | 'complaint' | 'surgery' | 'medication' | 'admission';
}

export interface MedicalHistory {
  patient_id: string;
  conditions: MedicalCondition[];
  medications: Medication[];
  allergies: string[];
  surgical_history?: string[];
  family_history?: string[];
}

export interface ClinicalSummary {
  patient_id: string;
  current_complaint: string;
  duration: string;
  severity: string;
  associated_symptoms: string[];
  interview_summary: string;
  past_history: MedicalCondition[];
  medications: Medication[];
  allergies: string[];
  priority_flags: string[];
  missing_information: string[];
  status: PatientStatus;
  priority: PriorityLevel;
  arrival_time: string;
  timeline: TimelineEvent[];
  transcript: InterviewMessage[];
  verified_by?: string;
  verified_at?: string;
  doctor_notes?: string;
}

export interface Doctor {
  id: string;
  name: string;
  department: string;
  designation: string;
  hospital: string;
  avatar?: string;
}

export interface DashboardStats {
  patientsWaiting: number;
  interviewsCompleted: number;
  needsReview: number;
  priorityReviews: number;
}

export interface ExtractedFactItem {
  field_name: string;
  value: string;
  status: string;
}

export interface BackendInterviewStartResponse {
  interview_id: string;
  patient_id: string;
  status: string;
  language: string;
  started_at?: string;
  initial_question?: {
    text: string;
    type: string;
  };
}

export interface BackendInterviewRespondResponse {
  interview_id: string;
  status: string;
  received_message: string;
  extracted_facts: ExtractedFactItem[];
  current_topic: string;
  next_question: {
    text: string;
    type: string;
  };
  interview_completed: boolean;
}

export interface BackendInterviewVoiceResponse {
  interview_id: string;
  status: string;
  transcript: string;
  received_message: string;
  extracted_facts: ExtractedFactItem[];
  current_topic: string;
  next_question: {
    text: string;
    type: string;
  };
  interview_completed: boolean;
}

export interface BackendInterviewDetailResponse {
  interview_id: string;
  patient_id: string;
  status: string;
  language: string;
  current_topic?: string;
  started_at?: string;
  completed_at?: string;
  messages: {
    id: number;
    interview_id: string;
    role: string;
    text: string;
    language: string;
    timestamp: string;
  }[];
}

export interface DoctorSnapshotData {
  patient_id: string;
  name: string;
  age?: number;
  gender?: string;
  preferred_language?: string;
  uhid?: string;
  phone?: string;
  registration_time?: string;
}

export interface DoctorSummaryResponse {
  record_revision?: number;
  patient_snapshot: DoctorSnapshotData;
  current_complaint: {
    chief_complaint?: string;
    duration?: string;
    severity?: string;
    location?: string;
    trigger?: string;
    associated_symptoms?: string;
    facts: {
      field_name: string;
      value: string;
      status: string;
      source: string;
      confidence: number;
    }[];
  };
  past_medical_history: {
    condition: string;
    date?: string;
    source?: string;
    confidence?: number;
  }[];
  medications: {
    name: string;
    dosage?: string;
    frequency?: string;
    source?: string;
  }[];
  allergies: {
    allergen: string;
    reaction?: string;
    source?: string;
  }[];
  allergy_status: string;
  important_findings: {
    finding: string;
    value: string;
    category: string;
    status: string;
  }[];
  missing_information: {
    field_name: string;
    description: string;
    importance: string;
  }[];
  priority_flags: string[];
  interview_metadata: {
    interview_id?: string;
    status: string;
    language?: string;
    started_at?: string;
    completed_at?: string;
    current_topic?: string;
    total_messages?: number;
  };
  verification_status: string;
}

export interface DoctorNarrativeResponse {
  patient_id: string;
  patient_snapshot: string;
  presenting_complaint: string;
  interview_summary: string;
  relevant_history: string;
  medications: string;
  allergies: string;
  important_findings: string;
  missing_information: string;
  priority_flags: string;
  verification_note: string;
}

export interface DoctorEditAuditItem {
  audit_id: string;
  patient_id: string;
  interview_id?: string;
  field_name: string;
  original_value?: string | null;
  corrected_value?: string | null;
  changed_by: string;
  changed_at: string;
}

export interface DoctorSummaryEditRequest {
  chief_complaint?: string;
  duration?: string;
  severity?: string;
  location?: string;
  trigger?: string;
  associated_symptoms?: string;
  past_medical_history?: {
    condition: string;
    date?: string;
    source?: string;
    confidence?: number;
  }[];
  medications?: {
    name: string;
    dosage: string;
    frequency?: string;
    source?: string;
  }[];
  allergies?: {
    allergen: string;
    reaction?: string;
    source?: string;
  }[];
}

export interface DoctorSummaryEditResponse {
  patient_id: string;
  updated_fields: string[];
  verification_status: string;
  audit_entries: DoctorEditAuditItem[];
}

export interface DoctorSummaryVerifyResponse {
  patient_id: string;
  verification_status: string;
  verified_by: string;
  verified_at: string;
}

export interface PatientListItem {
  patient_id: string;
  name: string;
  age: number;
  gender: string;
  language: string;
  current_complaint?: string;
  duration?: string;
  severity?: string;
  status: string;
  priority: string;
  arrival_time?: string;
  registration_time?: string;
  uhid?: string;
}
