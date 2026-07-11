import api from './client'
import type {
  AuthTokens, LoginRequest, User, UserCreate, UserUpdate, PaginatedResponse,
  Patient, PatientCreate, PatientSummary, Allergy, AllergyCreate,
  Vaccine, ContinuousMedication,
  Appointment, AppointmentCreate,
  MedicalRecord, MedicalRecordCreate, Prescription, ExamRequest,
  AnalysisJob, AnalysisType,
  ReportJob, ReportType, OutputFormat, DashboardSummary,
} from '@/types'

// ─── Auth ──────────────────────────────────────────────────────────────────
export const authApi = {
  login: (data: LoginRequest) =>
    api.post<AuthTokens>('/auth/login', data).then(r => r.data),

  logout: (refresh_token: string) =>
    api.post('/auth/logout', { refresh_token }),

  refresh: (refresh_token: string) =>
    api.post<AuthTokens>('/auth/refresh', { refresh_token }).then(r => r.data),

  changePassword: (current_password: string, new_password: string) =>
    api.post('/auth/change-password', { current_password, new_password }),

  requestPasswordReset: (email: string) =>
    api.post('/auth/password/reset', { email }),

  verifyTwoFactor: (email: string, code: string) =>
    api.post('/auth/2fa/verify', { email, code }),

  me: () => api.get<User>('/users/me').then(r => r.data),

  // OAuth — list linked accounts
  listOAuthAccounts: () =>
    api.get<{ accounts: Array<{ provider: string; email: string }> }>('/auth/oauth/accounts').then(r => r.data),
}

// ─── Users ─────────────────────────────────────────────────────────────────
export const usersApi = {
  list: (params?: { page?: number; size?: number; role?: string; is_active?: boolean }) =>
    api.get<PaginatedResponse<User>>('/users', { params }).then(r => r.data),

  get: (id: string) => api.get<User>(`/users/${id}`).then(r => r.data),

  create: (data: UserCreate) => api.post<User>('/users', data).then(r => r.data),

  update: (id: string, data: UserUpdate) =>
    api.put<User>(`/users/${id}`, data).then(r => r.data),

  assignRole: (id: string, role: string) =>
    api.put<User>(`/users/${id}/role`, { role }).then(r => r.data),

  deactivate: (id: string, reason: string) =>
    api.delete(`/users/${id}`, { data: { reason } }),

  // Doctors listing — accessible for patients
  listDoctors: () =>
    api.get<{ items: User[]; total: number }>('/users/doctors').then(r => r.data),
}

// ─── Patients ───────────────────────────────────────────────────────────────
export const patientsApi = {
  list: (params?: { page?: number; size?: number; search?: string }) =>
    api.get<PaginatedResponse<Patient>>('/patients', { params }).then(r => r.data),

  get: (id: string) => api.get<Patient>(`/patients/${id}`).then(r => r.data),

  summary: (id: string) =>
    api.get<PatientSummary>(`/patients/${id}/summary`).then(r => r.data),

  create: (data: PatientCreate) =>
    api.post<Patient>('/patients', data).then(r => r.data),

  update: (id: string, data: Partial<PatientCreate>) =>
    api.put<Patient>(`/patients/${id}`, data).then(r => r.data),

  deactivate: (id: string) => api.delete(`/patients/${id}`),

  // Allergies
  listAllergies: (patientId: string) =>
    api.get<Allergy[]>(`/patients/${patientId}/allergies`).then(r => r.data),

  addAllergy: (patientId: string, data: AllergyCreate) =>
    api.post<Allergy>(`/patients/${patientId}/allergies`, data).then(r => r.data),

  deleteAllergy: (patientId: string, allergyId: string) =>
    api.delete(`/patients/${patientId}/allergies/${allergyId}`),

  // Vaccines
  listVaccines: (patientId: string) =>
    api.get<Vaccine[]>(`/patients/${patientId}/vaccines`).then(r => r.data),

  addVaccine: (patientId: string, data: Partial<Vaccine>) =>
    api.post<Vaccine>(`/patients/${patientId}/vaccines`, data).then(r => r.data),

  // Medications
  listMedications: (patientId: string, active_only = false) =>
    api.get<ContinuousMedication[]>(`/patients/${patientId}/medications`, {
      params: { active_only },
    }).then(r => r.data),

  addMedication: (patientId: string, data: Partial<ContinuousMedication>) =>
    api.post<ContinuousMedication>(`/patients/${patientId}/medications`, data).then(r => r.data),

  deleteMedication: (patientId: string, medId: string) =>
    api.delete(`/patients/${patientId}/medications/${medId}`),
}

// ─── Appointments ───────────────────────────────────────────────────────────
export const appointmentsApi = {
  list: (params?: {
    page?: number; size?: number; patient_id?: string;
    doctor_id?: string; status?: string; from_date?: string; to_date?: string;
  }) => api.get<PaginatedResponse<Appointment>>('/appointments', { params }).then(r => r.data),

  get: (id: string) => api.get<Appointment>(`/appointments/${id}`).then(r => r.data),

  create: (data: AppointmentCreate) =>
    api.post<Appointment>('/appointments', data).then(r => r.data),

  cancel: (id: string, reason: string) =>
    api.put<Appointment>(`/appointments/${id}/cancel`, { reason }).then(r => r.data),

  complete: (id: string) =>
    api.put<Appointment>(`/appointments/${id}/complete`).then(r => r.data),
}

// ─── Medical Records ────────────────────────────────────────────────────────
export const recordsApi = {
  listByPatient: (patientId: string, params?: { page?: number; size?: number }) =>
    api.get<{ items: MedicalRecord[]; total: number; page: number; size: number }>(
      `/records/patient/${patientId}`,
      { params }
    ).then(r => r.data),

  get: (id: string) => api.get<MedicalRecord>(`/records/${id}`).then(r => r.data),

  create: (data: MedicalRecordCreate) =>
    api.post<MedicalRecord>('/records', data).then(r => r.data),

  update: (id: string, data: Partial<MedicalRecordCreate>) =>
    api.put<MedicalRecord>(`/records/${id}`, data).then(r => r.data),

  // Prescriptions
  createPrescription: (recordId: string, data: {
    medications: Array<{ name: string; dosage: string; frequency: string; duration_days: number; instructions?: string }>
    instructions?: string; valid_days?: number
  }) => api.post<Prescription>(`/records/${recordId}/prescriptions`, data).then(r => r.data),

  downloadPrescription: (recordId: string, prescriptionId: string) =>
    api.get(`/records/${recordId}/prescriptions/${prescriptionId}/pdf`, {
      responseType: 'blob',
    }),

  // Exams
  createExam: (recordId: string, data: { exam_type: string; urgency: string; instructions?: string }) =>
    api.post<ExamRequest>(`/records/${recordId}/exams`, data).then(r => r.data),

  recordResult: (recordId: string, examId: string, data: { result: string; result_date?: string }) =>
    api.put<ExamRequest>(`/records/${recordId}/exams/${examId}/result`, data).then(r => r.data),
}

// ─── AI ─────────────────────────────────────────────────────────────────────
export const aiApi = {
  analyze: (data: { analysis_type: AnalysisType; patient_id: string; record_id?: string; context?: object }) =>
    api.post<{ job_id: string; status: string }>('/ai/analyze', data).then(r => r.data),

  getJob: (jobId: string) => api.get<AnalysisJob>(`/ai/jobs/${jobId}`).then(r => r.data),

  listByRecord: (recordId: string) =>
    api.get<{ items: AnalysisJob[]; total: number }>(`/ai/records/${recordId}/analyses`).then(r => r.data),
}

// ─── Reports ────────────────────────────────────────────────────────────────
export const reportsApi = {
  summary: () => api.get<DashboardSummary>('/reports/summary').then(r => r.data),

  consultations: (params?: { from_date?: string; to_date?: string }) =>
    api.get('/reports/consultations', { params }).then(r => r.data),

  patients: (params?: { from_date?: string; to_date?: string }) =>
    api.get('/reports/patients', { params }).then(r => r.data),

  doctors: (params?: { doctor_id?: string; from_date?: string; to_date?: string }) =>
    api.get('/reports/doctors', { params }).then(r => r.data),

  requestExport: (data: { report_type: ReportType; output_format: OutputFormat; parameters?: object }) =>
    api.post<{ job_id: string; status: string }>('/reports/export', data).then(r => r.data),

  getExportJob: (jobId: string) =>
    api.get<ReportJob>(`/reports/export/${jobId}`).then(r => r.data),

  downloadExport: (jobId: string) =>
    api.get(`/reports/export/${jobId}/download`, { responseType: 'blob' }),
}

// ─── Audit ──────────────────────────────────────────────────────────────────
export const auditApi = {
  logs: (params?: {
    service?: string; table_name?: string; operation?: string;
    user_id?: string; from_date?: string; to_date?: string;
    page?: number; size?: number;
  }) => api.get<{ items: Record<string, unknown>[]; total: number; page: number; size: number }>(
    '/audit/logs', { params }
  ).then(r => r.data),

  summary: (params?: { from_date?: string; to_date?: string }) =>
    api.get<{
      period: { from: string; to: string };
      total: number;
      by_operation: Record<string, number>;
      by_service: Record<string, number>;
      by_table: Record<string, number>;
    }>('/audit/summary', { params }).then(r => r.data),

  suspicious: () =>
    api.get<{
      alerts: Array<{
        type: string; severity: string; service: string;
        user_id?: string; user_email?: string; count: number; period_hour?: string;
      }>;
      total_alerts: number; period_days: number; generated_at: string;
    }>('/audit/suspicious').then(r => r.data),
}
