// ─── Auth ──────────────────────────────────────────────────────────────────

export type Role = 'ADMIN' | 'DOCTOR' | 'ATTENDANT' | 'PATIENT'

export interface TokenPayload {
  sub: string
  role: Role
  email: string
  exp: number
  iat: number
  type: 'access' | 'refresh'
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface LoginRequest {
  email: string
  password: string
}

// ─── Users ─────────────────────────────────────────────────────────────────

export interface User {
  id: string
  email: string
  full_name: string
  role: Role
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface UserCreate {
  email: string
  password: string
  full_name: string
  role: Role
}

export interface UserUpdate {
  full_name?: string
  email?: string
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

// ─── Patients ───────────────────────────────────────────────────────────────

export interface Patient {
  id: string
  user_id: string
  full_name: string
  cpf: string | null
  date_of_birth: string | null
  gender: 'M' | 'F' | 'OTHER' | null
  blood_type: string | null
  phone: string | null
  email: string | null
  street: string | null
  city: string | null
  state: string | null
  zip_code: string | null
  emergency_name: string | null
  emergency_phone: string | null
  emergency_relation: string | null
  notes: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface PatientSummary extends Patient {
  allergies: Allergy[]
  medications: ContinuousMedication[]
}

export interface PatientCreate {
  user_id: string
  full_name: string
  cpf?: string
  date_of_birth?: string
  gender?: 'M' | 'F' | 'OTHER'
  blood_type?: string
  phone?: string
  email?: string
  address?: { street?: string; city?: string; state?: string; zip_code?: string }
  emergency_contact?: { name?: string; phone?: string; relation?: string }
  notes?: string
}

export interface Allergy {
  id: string
  patient_id: string
  substance: string
  severity: 'MILD' | 'MODERATE' | 'SEVERE'
  reaction_type: string | null
  notes: string | null
  created_at: string
}

export interface AllergyCreate {
  substance: string
  severity: 'MILD' | 'MODERATE' | 'SEVERE'
  reaction_type?: string
  notes?: string
}

export interface Vaccine {
  id: string
  patient_id: string
  name: string
  dose: string | null
  applied_at: string | null
  next_dose_at: string | null
  notes: string | null
  created_at: string
}

export interface ContinuousMedication {
  id: string
  patient_id: string
  name: string
  dosage: string
  frequency: string
  prescribing_doctor: string | null
  started_at: string | null
  active: boolean
  notes: string | null
  created_at: string
}

// ─── Appointments ───────────────────────────────────────────────────────────

export type AppointmentType = 'CONSULTATION' | 'RETURN' | 'EXAM' | 'URGENT'
export type AppointmentStatus = 'SCHEDULED' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED' | 'NO_SHOW'

export interface Appointment {
  id: string
  patient_id: string
  doctor_id: string
  scheduled_at: string
  appointment_type: AppointmentType
  specialty: string | null
  status: AppointmentStatus
  cancellation_reason: string | null
  notes: string | null
  created_at: string
}

export interface AppointmentCreate {
  patient_id: string
  doctor_id: string
  scheduled_at: string
  appointment_type: AppointmentType
  specialty?: string
  notes?: string
  slot_id?: string
}

// ─── Medical Records ────────────────────────────────────────────────────────

export interface MedicalRecord {
  id: string
  appointment_id: string
  patient_id: string
  doctor_id: string
  chief_complaint: string
  anamnesis: string | null
  physical_exam: string | null
  diagnosis: string | null
  diagnosis_codes: string[]
  treatment_plan: string | null
  observations: string | null
  ai_analysis_id: string | null
  prescriptions: Prescription[]
  exam_requests: ExamRequest[]
  created_at: string
  updated_at: string
}

export interface MedicalRecordCreate {
  appointment_id: string
  chief_complaint: string
  anamnesis?: string
  physical_exam?: string
  diagnosis?: string
  diagnosis_codes?: string[]
  treatment_plan?: string
  observations?: string
}

export interface Prescription {
  id: string
  record_id: string
  patient_id: string
  doctor_id: string
  medications: MedicationItem[]
  instructions: string | null
  valid_days: number
  pdf_s3_key: string | null
  created_at: string
}

export interface MedicationItem {
  name: string
  dosage: string
  frequency: string
  duration_days: number
  instructions?: string
}

export interface ExamRequest {
  id: string
  record_id: string
  patient_id: string
  doctor_id: string
  exam_type: string
  urgency: 'ROUTINE' | 'URGENT' | 'EMERGENCY'
  instructions: string | null
  result: string | null
  result_date: string | null
  created_at: string
}

// ─── AI ─────────────────────────────────────────────────────────────────────

export type AnalysisType = 'DRUG_INTERACTION_CHECK' | 'SYMPTOM_ANALYSIS' | 'CLINICAL_SUMMARY'
export type JobStatus = 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'

export interface AnalysisJob {
  id: string
  analysis_type: AnalysisType
  patient_id: string
  record_id: string | null
  status: JobStatus
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null
  result: Record<string, unknown> | null
  model_version: string
  created_at: string
  completed_at: string | null
}

// ─── Reports ────────────────────────────────────────────────────────────────

export type ReportType = 'CONSULTATIONS' | 'PATIENTS' | 'DOCTORS' | 'PRESCRIPTIONS'
export type OutputFormat = 'JSON' | 'CSV' | 'PDF'

export interface ReportJob {
  id: string
  report_type: ReportType
  status: JobStatus
  output_format: OutputFormat
  row_count: number
  s3_key: string | null
  result_data: unknown | null
  error_message: string | null
  created_at: string
  completed_at: string | null
}

export interface DashboardSummary {
  consultations_today: number
  new_patients_this_month: number
  cancellations_today: number
  as_of: string
}

// ─── API Errors ─────────────────────────────────────────────────────────────

export interface ApiError {
  detail: string
  status?: number
}
