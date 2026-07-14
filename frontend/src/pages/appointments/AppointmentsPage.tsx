import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Calendar, Plus, X, CheckCircle, Clock, Search, Eye, FileText } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import {
  useAppointments, useCreateAppointment, useCancelAppointment, useConfirmAppointment,
  usePatients, useDoctors, useCreateRecord
} from '@/hooks'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Input, Textarea, Select, Modal,
  Table, Th, Td, Badge, PageLoader, EmptyState, Pagination,
  Alert, Spinner,
} from '@/components/ui'
import { formatDateTime, STATUS_LABELS, STATUS_COLORS, getErrorMessage, cn } from '@/utils'
import { useAuthStore, useIsPatient } from '@/store/auth.store'
import type { Appointment } from '@/types'

// ─── Create Appointment Modal ─────────────────────────────────────────────
const apptSchema = z.object({
  patient_id: z.string().optional(),
  doctor_id: z.string().min(1, 'Selecione o médico'),
  scheduled_at: z.string().min(1, 'Data obrigatória'),
  appointment_type: z.enum(['CONSULTATION', 'RETURN', 'EXAM', 'URGENT']),
  specialty: z.string().optional(),
  notes: z.string().optional(),
})
type ApptForm = z.infer<typeof apptSchema>

const TYPE_LABELS: Record<string, string> = {
  CONSULTATION: 'Consulta',
  RETURN: 'Retorno',
  EXAM: 'Exame',
  URGENT: 'Urgência',
}

function CreateAppointmentModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const createAppt = useCreateAppointment()
  const { data: patients } = usePatients({ size: 100 })
  const { data: doctors } = useDoctors()
  const isPatient = useIsPatient()

  const { register, handleSubmit, reset, formState: { errors } } = useForm<ApptForm>({
    resolver: zodResolver(apptSchema),
    defaultValues: { appointment_type: 'CONSULTATION' },
  })

  const onSubmit = async (data: ApptForm) => {
    setError(null)
    try {
      // Remove patient_id for patients — backend auto-assigns it
      const payload = isPatient
        ? { doctor_id: data.doctor_id, scheduled_at: new Date(data.scheduled_at).toISOString(), appointment_type: data.appointment_type, specialty: data.specialty, notes: data.notes }
        : { ...data, scheduled_at: new Date(data.scheduled_at).toISOString() }
      await createAppt.mutateAsync(payload)
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const patientOptions = patients?.items.map((p) => ({ value: p.id, label: p.full_name })) ?? []
  const doctorOptions = doctors?.items.map((d) => ({ value: d.id, label: d.full_name })) ?? []

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Agendar Consulta"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={createAppt.isPending}>Agendar</Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        {!isPatient && (
          <Select
            label="Paciente *"
            options={patientOptions}
            placeholder="Selecione o paciente"
            error={errors.patient_id?.message}
            {...register('patient_id')}
          />
        )}
        <Select
          label="Médico *"
          options={doctorOptions}
          placeholder="Selecione o médico"
          error={errors.doctor_id?.message}
          {...register('doctor_id')}
        />
        <div className="grid grid-cols-2 gap-4">
          <Select
            label="Tipo *"
            options={Object.entries(TYPE_LABELS).map(([v, l]) => ({ value: v, label: l }))}
            {...register('appointment_type')}
          />
          <Input
            label="Especialidade"
            placeholder="Clínica Geral"
            {...register('specialty')}
          />
        </div>
        <Input
          label="Data e hora *"
          type="datetime-local"
          error={errors.scheduled_at?.message}
          {...register('scheduled_at')}
        />
        <Input
          label="Observações"
          placeholder="Informações adicionais…"
          {...register('notes')}
        />
      </div>
    </Modal>
  )
}

// ─── Cancel Appointment Modal ─────────────────────────────────────────────
function CancelModal({
  appointment,
  open,
  onClose,
}: {
  appointment: Appointment | null
  open: boolean
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const cancel = useCancelAppointment()

  const handleCancel = async () => {
    if (!appointment || reason.trim().length < 5) return
    setError(null)
    try {
      await cancel.mutateAsync({ id: appointment.id, reason })
      setReason('')
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cancelar Consulta"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Voltar</Button>
          <Button
            variant="danger"
            onClick={handleCancel}
            loading={cancel.isPending}
            disabled={reason.trim().length < 5}
          >
            Confirmar Cancelamento
          </Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <Alert variant="warning" className="mb-4">
        ⚠ Pacientes devem cancelar com pelo menos 24h de antecedência.
      </Alert>
      <Input
        label="Motivo do cancelamento *"
        placeholder="Descreva o motivo…"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
    </Modal>
  )
}

// ─── Consultation Details Modal ───────────────────────────────────────────
function ConsultationDetailsModal({
  appointment,
  open,
  onClose,
}: {
  appointment: Appointment | null
  open: boolean
  onClose: () => void
  canCreateRecord: boolean
}) {
  const navigate = useNavigate()
  const createRecord = useCreateRecord()
  const [isCreating, setIsCreating] = useState(false)
  const [complaint, setComplaint] = useState('')
  const [anamnesis, setAnamnesis] = useState('')
  const [physicalExam, setPhysicalExam] = useState('')
  const [diagnosis, setDiagnosis] = useState('')
  const [treatmentPlan, setTreatmentPlan] = useState('')
  const [observations, setObservations] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (!appointment) return null

  const handleCreateRecord = async () => {
    if (complaint.trim().length < 5) {
      setError('A queixa principal deve ter pelo menos 5 caracteres')
      return
    }
    setError(null)
    try {
      const rec = await createRecord.mutateAsync({
        appointment_id: appointment.id,
        chief_complaint: complaint,
        anamnesis: anamnesis || undefined,
        physical_exam: physicalExam || undefined,
        diagnosis: diagnosis || undefined,
        treatment_plan: treatmentPlan || undefined,
        observations: observations || undefined,
      })
      onClose()
      navigate(`/records/${rec.id}`)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal
      open={open}
      onClose={() => { 
        setIsCreating(false); 
        setComplaint(''); 
        setAnamnesis('');
        setPhysicalExam('');
        setDiagnosis('');
        setTreatmentPlan('');
        setObservations('');
        onClose(); 
      }}
      title="Detalhes da Consulta"
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Fechar</Button>
          {canCreateRecord && !isCreating && appointment.status !== 'CANCELLED' && (
            <Button
              icon={<FileText className="w-4 h-4" />}
              onClick={() => setIsCreating(true)}
            >
              Criar Prontuário
            </Button>
          )}
        </>
      }
    >
      <div className="space-y-4">
        {error && <Alert variant="error">{error}</Alert>}
        <div className="grid grid-cols-2 gap-4 text-sm text-slate-300 bg-slate-900 p-4 rounded-xl border border-slate-800">
          <div>
            <span className="block text-slate-500 mb-1 text-xs">Horário</span>
            <span className="font-medium">{formatDateTime(appointment.scheduled_at)}</span>
          </div>
          <div>
            <span className="block text-slate-500 mb-1 text-xs">Status</span>
            <Badge className={STATUS_COLORS[appointment.status]}>{STATUS_LABELS[appointment.status]}</Badge>
          </div>
          <div>
            <span className="block text-slate-500 mb-1 text-xs">Tipo</span>
            {TYPE_LABELS[appointment.appointment_type]}
          </div>
          <div>
            <span className="block text-slate-500 mb-1 text-xs">Especialidade</span>
            {appointment.specialty || '—'}
          </div>
          {appointment.notes && (
            <div className="col-span-2">
              <span className="block text-slate-500 mb-1 text-xs">Observações do Agendamento</span>
              <p className="bg-slate-950 p-3 rounded-lg border border-slate-800">{appointment.notes}</p>
            </div>
          )}
        </div>

        {isCreating && (
          <div className="pt-4 border-t border-slate-800 space-y-4 animate-in fade-in slide-in-from-top-4 max-h-[60vh] overflow-y-auto pr-2 custom-scrollbar">
            <h4 className="font-semibold text-slate-200">Novo Prontuário</h4>
            <Input
              label="Queixa Principal *"
              placeholder="Descreva o motivo principal do atendimento..."
              value={complaint}
              onChange={(e) => setComplaint(e.target.value)}
            />
            <Textarea
              label="Anamnese"
              placeholder="Histórico da doença atual..."
              value={anamnesis}
              onChange={(e) => setAnamnesis(e.target.value)}
              rows={2}
            />
            <Textarea
              label="Exame Físico"
              value={physicalExam}
              onChange={(e) => setPhysicalExam(e.target.value)}
              rows={2}
            />
            <Textarea
              label="Hipótese Diagnóstica / CID"
              value={diagnosis}
              onChange={(e) => setDiagnosis(e.target.value)}
              rows={2}
            />
            <Textarea
              label="Conduta / Plano Terapêutico"
              value={treatmentPlan}
              onChange={(e) => setTreatmentPlan(e.target.value)}
              rows={2}
            />
            <Textarea
              label="Observações Adicionais"
              value={observations}
              onChange={(e) => setObservations(e.target.value)}
              rows={2}
            />
            <div className="flex justify-end gap-2 pt-2">
              <Button variant="ghost" onClick={() => setIsCreating(false)}>Cancelar</Button>
              <Button onClick={handleCreateRecord} loading={createRecord.isPending}>
                Salvar Prontuário
              </Button>
            </div>
          </div>
        )}
      </div>
    </Modal>
  )
}

// ─── Appointment Row ──────────────────────────────────────────────────────
function AppointmentRow({
  appt,
  canCancel,
  onCancel,
  onConfirm,
  onDetails,
}: {
  appt: Appointment
  canConfirm: boolean
  canCancel: boolean
  onCancel: (appt: Appointment) => void
  onConfirm: (appt: Appointment) => void
  onDetails: (appt: Appointment) => void
}) {
  return (
    <tr className="hover:bg-slate-800/20 transition-colors">
      <Td>
        <div className="flex items-center gap-2">
          <Clock className="w-3.5 h-3.5 text-slate-600" />
          <span className="font-medium text-slate-200">{formatDateTime(appt.scheduled_at)}</span>
        </div>
      </Td>
      <Td>
        <span className="font-medium text-slate-200">{appt.patient_name || 'Desconhecido'}</span>
      </Td>
      <Td>
        <Badge className="bg-slate-700/40 text-slate-300 ring-slate-600/30">
          {TYPE_LABELS[appt.appointment_type]}
        </Badge>
      </Td>
      <Td>{appt.specialty ?? '—'}</Td>
      <Td>
        <Badge className={STATUS_COLORS[appt.status]}>
          {STATUS_LABELS[appt.status]}
        </Badge>
      </Td>
      <Td>
        <div className="flex items-center gap-2 justify-end">
          <Button
            variant="ghost"
            size="sm"
            icon={<Eye className="w-3.5 h-3.5 text-slate-400" />}
            onClick={() => onDetails(appt)}
          >
            Detalhes
          </Button>
          {canConfirm && appt.status === 'SCHEDULED' && (
            <Button
              variant="ghost"
              size="sm"
              icon={<CheckCircle className="w-3.5 h-3.5 text-brand-400" />}
              onClick={() => onConfirm(appt)}
            >
              Confirmar
            </Button>
          )}
          {canCancel && appt.status === 'SCHEDULED' && (
            <Button
              variant="ghost"
              size="sm"
              className="text-red-400 hover:text-red-300 hover:bg-red-400/10"
              icon={<X className="w-3.5 h-3.5" />}
              onClick={() => onCancel(appt)}
            >
              Cancelar
            </Button>
          )}
        </div>
      </Td>
    </tr>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────
export function AppointmentsPage() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [patientNameFilter, setPatientNameFilter] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [cancelTarget, setCancelTarget] = useState<Appointment | null>(null)
  const [detailsTarget, setDetailsTarget] = useState<Appointment | null>(null)

  const { role } = useAuthStore()
  const canCreate = role === 'ADMIN' || role === 'ATTENDANT' || role === 'PATIENT'
  const canCancel = true // all roles can cancel (business rules enforced backend-side)
  const canConfirm = role !== 'PATIENT'

  const confirm = useConfirmAppointment()

  const { data, isLoading } = useAppointments({
    page,
    size: 20,
    status: statusFilter || undefined,
    patient_name: patientNameFilter || undefined,
  })

  const handleConfirm = async (appt: Appointment) => {
    try {
      await confirm.mutateAsync(appt.id)
    } catch (err) {
      console.error(err)
      alert(getErrorMessage(err))
    }
  }

  return (
    <div>
      <PageHeader
        title="Consultas"
        description="Gerencie sua agenda de atendimentos, agendamentos e retornos."
        action={
          canCreate ? (
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>
              Agendar Consulta
            </Button>
          ) : undefined
        }
      />

      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <h3 className="font-semibold text-slate-200">Próximos Agendamentos</h3>
            <div className="flex bg-slate-800/50 p-1 rounded-lg border border-slate-700/50">
              {['', 'SCHEDULED', 'CONFIRMED', 'COMPLETED', 'CANCELLED'].map((s) => (
                <button
                  key={s}
                  onClick={() => {
                    setStatusFilter(s)
                    setPage(1)
                  }}
                  className={cn(
                    'px-3 py-1.5 rounded-lg text-xs font-medium transition-all',
                    statusFilter === s
                      ? 'bg-brand-500/15 text-brand-300'
                      : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/40'
                  )}
                >
                  {s === '' ? 'Todas' : STATUS_LABELS[s]}
                </button>
              ))}
            </div>
          </div>
          
          <div className="mt-4 flex max-w-sm">
            <Input
              placeholder="Pesquisar por paciente..."
              value={patientNameFilter}
              onChange={(e) => {
                setPatientNameFilter(e.target.value)
                setPage(1)
              }}
            />
          </div>
        </CardHeader>

        {isLoading ? (
          <PageLoader />
        ) : !data?.items.length ? (
          <CardBody>
            <EmptyState
              icon={<Calendar className="w-8 h-8" />}
              title="Nenhuma consulta encontrada"
              action={
                canCreate ? (
                  <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>
                    Agendar
                  </Button>
                ) : undefined
              }
            />
          </CardBody>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Data / Hora</Th>
                  <Th>Paciente</Th>
                  <Th>Tipo</Th>
                  <Th>Especialidade</Th>
                  <Th>Status</Th>
                  <Th>Ações</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((appt) => (
                  <AppointmentRow
                    key={appt.id}
                    appt={appt}
                    canConfirm={canConfirm}
                    canCancel={canCancel}
                    onCancel={setCancelTarget}
                    onConfirm={handleConfirm}
                    onDetails={setDetailsTarget}
                  />
                ))}
              </tbody>
            </Table>
            <Pagination page={page} total={data.total} size={20} onChange={setPage} />
          </>
        )}
      </Card>

      <CreateAppointmentModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <CancelModal
        appointment={cancelTarget}
        open={!!cancelTarget}
        onClose={() => setCancelTarget(null)}
      />
      <ConsultationDetailsModal
        appointment={detailsTarget}
        open={!!detailsTarget}
        onClose={() => setDetailsTarget(null)}
        canCreateRecord={role !== 'PATIENT'}
      />
    </div>
  )
}
