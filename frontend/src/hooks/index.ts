import { useQuery, useMutation, useQueryClient, useInfiniteQuery } from '@tanstack/react-query'
import {
  usersApi, patientsApi, appointmentsApi, recordsApi, aiApi, reportsApi
} from '@/api/services'
import type {
  UserCreate, UserUpdate, PatientCreate, AllergyCreate, VaccineCreate, AppointmentCreate,
  MedicalRecordCreate, AnalysisType, ReportType, OutputFormat
} from '@/types'

// ─── Query Keys ────────────────────────────────────────────────────────────
export const keys = {
  users: {
    all: ['users'] as const,
    list: (params?: object) => ['users', 'list', params] as const,
    detail: (id: string) => ['users', id] as const,
  },
  patients: {
    all: ['patients'] as const,
    list: (params?: object) => ['patients', 'list', params] as const,
    detail: (id: string) => ['patients', id] as const,
    summary: (id: string) => ['patients', id, 'summary'] as const,
    allergies: (id: string) => ['patients', id, 'allergies'] as const,
    vaccines: (id: string) => ['patients', id, 'vaccines'] as const,
    medications: (id: string) => ['patients', id, 'medications'] as const,
  },
  appointments: {
    all: ['appointments'] as const,
    list: (params?: object) => ['appointments', 'list', params] as const,
    detail: (id: string) => ['appointments', id] as const,
  },
  records: {
    all: ['records'] as const,
    byPatient: (patientId: string) => ['records', 'patient', patientId] as const,
    detail: (id: string) => ['records', id] as const,
  },
  ai: {
    job: (jobId: string) => ['ai', 'job', jobId] as const,
    byRecord: (recordId: string) => ['ai', 'record', recordId] as const,
  },
  reports: {
    summary: ['reports', 'summary'] as const,
    consultations: (params?: object) => ['reports', 'consultations', params] as const,
    job: (jobId: string) => ['reports', 'job', jobId] as const,
  },
}

// ─── Users ─────────────────────────────────────────────────────────────────
export function useUsers(params?: { page?: number; size?: number; role?: string; is_active?: boolean }) {
  return useQuery({
    queryKey: keys.users.list(params),
    queryFn: () => usersApi.list(params),
  })
}

export function useUser(id: string) {
  return useQuery({
    queryKey: keys.users.detail(id),
    queryFn: () => usersApi.get(id),
    enabled: !!id,
  })
}

export function useCreateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: UserCreate) => usersApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.users.all }),
  })
}

export function useDoctors() {
  return useQuery({
    queryKey: ['users', 'doctors'],
    queryFn: () => usersApi.listDoctors(),
  })
}

export function useDeactivateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      usersApi.deactivate(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.users.all }),
  })
}

export function useUpdateUser() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<UserUpdate> }) =>
      usersApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.users.all }),
  })
}

// ─── Patients ───────────────────────────────────────────────────────────────
export function usePatients(params?: { page?: number; size?: number; search?: string }) {
  return useQuery({
    queryKey: keys.patients.list(params),
    queryFn: () => patientsApi.list(params),
  })
}

export function usePatient(id: string) {
  return useQuery({
    queryKey: keys.patients.detail(id),
    queryFn: () => patientsApi.get(id),
    enabled: !!id,
  })
}

export function useMyPatient() {
  return useQuery({
    queryKey: ['patients', 'me'],
    queryFn: () => patientsApi.me(),
  })
}

export function usePatientSummary(id: string) {
  return useQuery({
    queryKey: keys.patients.summary(id),
    queryFn: () => patientsApi.summary(id),
    enabled: !!id,
  })
}

export function usePatientAllergies(patientId: string) {
  return useQuery({
    queryKey: keys.patients.allergies(patientId),
    queryFn: () => patientsApi.listAllergies(patientId),
    enabled: !!patientId,
  })
}

export function usePatientVaccines(patientId: string) {
  return useQuery({
    queryKey: keys.patients.vaccines(patientId),
    queryFn: () => patientsApi.listVaccines(patientId),
    enabled: !!patientId,
  })
}

export function usePatientMedications(patientId: string) {
  return useQuery({
    queryKey: keys.patients.medications(patientId),
    queryFn: () => patientsApi.listMedications(patientId),
    enabled: !!patientId,
  })
}

export function useCreatePatient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: PatientCreate) => patientsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.patients.all }),
  })
}

export function useUpdatePatient() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<PatientCreate> }) =>
      patientsApi.update(id, data),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: keys.patients.detail(id) })
      qc.invalidateQueries({ queryKey: keys.patients.summary(id) })
      qc.invalidateQueries({ queryKey: ['patients', 'me'] })
    },
  })
}

export function useAddVaccine() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ patientId, data }: { patientId: string; data: VaccineCreate }) =>
      patientsApi.addVaccine(patientId, data),
    onSuccess: (_, { patientId }) =>
      qc.invalidateQueries({ queryKey: keys.patients.vaccines(patientId) }),
  })
}

export function useAddAllergy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ patientId, data }: { patientId: string; data: AllergyCreate }) =>
      patientsApi.addAllergy(patientId, data),
    onSuccess: (_, { patientId }) =>
      qc.invalidateQueries({ queryKey: keys.patients.allergies(patientId) }),
  })
}

export function useDeleteAllergy() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ patientId, allergyId }: { patientId: string; allergyId: string }) =>
      patientsApi.deleteAllergy(patientId, allergyId),
    onSuccess: (_, { patientId }) =>
      qc.invalidateQueries({ queryKey: keys.patients.allergies(patientId) }),
  })
}

export function useAddMedication() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ patientId, data }: { patientId: string; data: { name: string; dosage: string; frequency: string; prescribing_doctor?: string; started_at?: string; notes?: string } }) =>
      patientsApi.addMedication(patientId, data),
    onSuccess: (_, { patientId }) =>
      qc.invalidateQueries({ queryKey: keys.patients.medications(patientId) }),
  })
}

export function useDeleteMedication() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ patientId, medId }: { patientId: string; medId: string }) =>
      patientsApi.deleteMedication(patientId, medId),
    onSuccess: (_, { patientId }) =>
      qc.invalidateQueries({ queryKey: keys.patients.medications(patientId) }),
  })
}

// ─── Appointments ───────────────────────────────────────────────────────────
export function useAppointments(params?: object) {
  return useQuery({
    queryKey: keys.appointments.list(params),
    queryFn: () => appointmentsApi.list(params),
  })
}

export function useAppointment(id: string) {
  return useQuery({
    queryKey: keys.appointments.detail(id),
    queryFn: () => appointmentsApi.get(id),
    enabled: !!id,
  })
}

export function useCreateAppointment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: AppointmentCreate) => appointmentsApi.create(data),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.appointments.all }),
  })
}

export function useCancelAppointment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      appointmentsApi.cancel(id, reason),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.appointments.all }),
  })
}

export function useConfirmAppointment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => appointmentsApi.confirm(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.appointments.all }),
  })
}

// ─── Medical Records ────────────────────────────────────────────────────────
export function usePatientRecords(patientId: string) {
  return useQuery({
    queryKey: keys.records.byPatient(patientId),
    queryFn: () => recordsApi.listByPatient(patientId),
    enabled: !!patientId,
  })
}

export function useRecords() {
  return useQuery({
    queryKey: keys.records.all,
    queryFn: () => recordsApi.list(),
  })
}

export function useRecord(id: string) {
  return useQuery({
    queryKey: keys.records.detail(id),
    queryFn: () => recordsApi.get(id),
    enabled: !!id,
  })
}

export function useCreateRecord() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: MedicalRecordCreate) => recordsApi.create(data),
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: keys.records.byPatient(data.patient_id) })
    },
  })
}

export function useCreatePrescription() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ recordId, data }: {
      recordId: string;
      data: { medications: Array<{ name: string; dosage: string; frequency: string; duration_days: number }>; instructions?: string; valid_days?: number }
    }) => recordsApi.createPrescription(recordId, data),
    onSuccess: (_, { recordId }) =>
      qc.invalidateQueries({ queryKey: keys.records.detail(recordId) }),
  })
}

// ─── AI ─────────────────────────────────────────────────────────────────────
export function useAnalysisJob(jobId: string, enabled = true) {
  return useQuery({
    queryKey: keys.ai.job(jobId),
    queryFn: () => aiApi.getJob(jobId),
    enabled: !!jobId && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'PENDING' || status === 'RUNNING' ? 3000 : false
    },
  })
}

export function useRecordAnalyses(recordId: string) {
  return useQuery({
    queryKey: keys.ai.byRecord(recordId),
    queryFn: () => aiApi.listByRecord(recordId),
    enabled: !!recordId,
  })
}

export function useRequestAnalysis() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { analysis_type: AnalysisType; patient_id: string; record_id?: string; context?: object }) =>
      aiApi.analyze(data),
  })
}

// ─── Reports ────────────────────────────────────────────────────────────────
export function useDashboardSummary() {
  return useQuery({
    queryKey: keys.reports.summary,
    queryFn: () => reportsApi.summary(),
    refetchInterval: 60_000,
  })
}

export function useConsultationsReport(params?: object) {
  return useQuery({
    queryKey: keys.reports.consultations(params),
    queryFn: () => reportsApi.consultations(params),
  })
}

export function useExportJob(jobId: string, enabled = true) {
  return useQuery({
    queryKey: keys.reports.job(jobId),
    queryFn: () => reportsApi.getExportJob(jobId),
    enabled: !!jobId && enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'PENDING' || status === 'RUNNING' ? 5000 : false
    },
  })
}

export function useRequestExport() {
  return useMutation({
    mutationFn: (data: { report_type: ReportType; output_format: OutputFormat; parameters?: object }) =>
      reportsApi.requestExport(data),
  })
}
