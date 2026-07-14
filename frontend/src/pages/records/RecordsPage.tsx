import { useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  FileText, Plus, ArrowLeft, Pill, FlaskConical,
  Brain, Download, ChevronRight, Stethoscope,
  ClipboardList, AlertTriangle,
} from 'lucide-react'
import {
  usePatientRecords, useRecords, useRecord, useCreateRecord,
  useCreatePrescription, useRecordAnalyses, useRequestAnalysis,
  useAppointments,
} from '@/hooks'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Input, Textarea, Select,
  Badge, PageLoader, EmptyState, Modal, Alert, Table, Th, Td, Spinner,
} from '@/components/ui'
import { formatDate, formatDateTime, formatRelative, RISK_COLORS, getErrorMessage, cn } from '@/utils'
import { useIsDoctor, useIsPatient, useAuthStore } from '@/store/auth.store'
import { recordsApi } from '@/api/services'
import type { MedicalRecord } from '@/types'

// ─── Create Record Modal ──────────────────────────────────────────────────
const recordSchema = z.object({
  appointment_id: z.string().min(1, 'Selecione uma consulta'),
  chief_complaint: z.string().min(5, 'Queixa principal obrigatória'),
  anamnesis: z.string().optional(),
  physical_exam: z.string().optional(),
  diagnosis: z.string().optional(),
  treatment_plan: z.string().optional(),
  observations: z.string().optional(),
})
type RecordForm = z.infer<typeof recordSchema>

function CreateRecordModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const createRecord = useCreateRecord()
  const { data: appointments } = useAppointments({ status: 'SCHEDULED', page: 1, size: 50 })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<RecordForm>({
    resolver: zodResolver(recordSchema),
  })

  const onSubmit = async (data: RecordForm) => {
    setError(null)
    try {
      await createRecord.mutateAsync(data)
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const apptOptions = appointments?.items.map((a) => ({
    value: a.id,
    label: `${formatDateTime(a.scheduled_at)} — ${a.specialty ?? a.appointment_type}`,
  })) ?? []

  return (
    <Modal open={open} onClose={onClose} title="Novo Prontuário" size="xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={createRecord.isPending}>Criar Prontuário</Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        <Select
          label="Consulta *"
          options={apptOptions}
          placeholder="Selecione a consulta"
          error={errors.appointment_id?.message}
          {...register('appointment_id')}
        />
        <Textarea
          label="Queixa principal *"
          placeholder="Paciente refere…"
          rows={2}
          error={errors.chief_complaint?.message}
          {...register('chief_complaint')}
        />
        <Textarea label="Anamnese" placeholder="Histórico clínico…" rows={3} {...register('anamnesis')} />
        <Textarea label="Exame físico" placeholder="PA, FC, ausculta…" rows={2} {...register('physical_exam')} />
        <div className="grid grid-cols-2 gap-4">
          <Textarea label="Diagnóstico" rows={2} {...register('diagnosis')} />
          <Textarea label="Plano terapêutico" rows={2} {...register('treatment_plan')} />
        </div>
        <Textarea label="Observações" rows={2} {...register('observations')} />
      </div>
    </Modal>
  )
}

// ─── Prescription Modal ───────────────────────────────────────────────────
const prescriptionSchema = z.object({
  medications: z.array(z.object({
    name: z.string().min(1),
    dosage: z.string().min(1),
    frequency: z.string().min(1),
    duration_days: z.coerce.number().min(1),
    instructions: z.string().optional(),
  })).min(1, 'Adicione ao menos um medicamento'),
  instructions: z.string().optional(),
  valid_days: z.coerce.number().default(30),
})
type PrescriptionForm = z.infer<typeof prescriptionSchema>

function PrescriptionModal({ recordId, open, onClose }: { recordId: string; open: boolean; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const createPrescription = useCreatePrescription()

  const { register, handleSubmit, control, reset, formState: { errors } } = useForm<PrescriptionForm>({
    resolver: zodResolver(prescriptionSchema),
    defaultValues: { medications: [{ name: '', dosage: '', frequency: '', duration_days: 7 }], valid_days: 30 },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'medications' })

  const onSubmit = async (data: PrescriptionForm) => {
    setError(null)
    try {
      await createPrescription.mutateAsync({ recordId, data })
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Nova Prescrição" size="xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={createPrescription.isPending}>
            Gerar Prescrição
          </Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        {fields.map((field, i) => (
          <div key={field.id} className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/60 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Medicamento {i + 1}</span>
              {i > 0 && (
                <button onClick={() => remove(i)} className="text-xs text-rose-400 hover:underline">
                  Remover
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Nome *" placeholder="Dipirona" {...register(`medications.${i}.name`)} />
              <Input label="Dosagem *" placeholder="500mg" {...register(`medications.${i}.dosage`)} />
              <Input label="Frequência *" placeholder="6/6h" {...register(`medications.${i}.frequency`)} />
              <Input label="Dias *" type="number" placeholder="7" {...register(`medications.${i}.duration_days`)} />
            </div>
            <Input label="Instruções" placeholder="Tomar com água…" {...register(`medications.${i}.instructions`)} />
          </div>
        ))}

        <Button
          variant="outline"
          size="sm"
          icon={<Plus className="w-3.5 h-3.5" />}
          onClick={() => append({ name: '', dosage: '', frequency: '', duration_days: 7 })}
        >
          Adicionar medicamento
        </Button>

        <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-800">
          <Textarea label="Instruções gerais" rows={2} {...register('instructions')} />
          <Input label="Validade (dias)" type="number" {...register('valid_days')} />
        </div>
      </div>
    </Modal>
  )
}

// ─── Record Card ──────────────────────────────────────────────────────────
function RecordCard({ record }: { record: MedicalRecord }) {
  const navigate = useNavigate()
  return (
    <Card hover onClick={() => navigate(`/records/${record.id}`)} className="p-5">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-brand-500/10 flex items-center justify-center flex-shrink-0">
            <FileText className="w-4 h-4 text-brand-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-200 line-clamp-1">{record.chief_complaint}</p>
            <p className="text-xs text-slate-500 mt-0.5">{formatDateTime(record.created_at)}</p>
            <p className="text-[10px] text-slate-600 mt-0.5 font-mono">ID: {record.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          {record.prescriptions.length > 0 && (
            <Badge className="bg-violet-500/15 text-violet-300 ring-violet-500/20">
              {record.prescriptions.length} Rx
            </Badge>
          )}
          {record.exam_requests.length > 0 && (
            <Badge className="bg-sky-500/15 text-sky-300 ring-sky-500/20">
              {record.exam_requests.length} exames
            </Badge>
          )}
          <ChevronRight className="w-4 h-4 text-slate-600" />
        </div>
      </div>
      {record.diagnosis && (
        <p className="text-xs text-slate-500 mt-3 pl-12">
          <span className="text-slate-600">Diagnóstico:</span> {record.diagnosis}
        </p>
      )}
    </Card>
  )
}

// ─── Record Detail View ───────────────────────────────────────────────────
function RecordDetailView({ recordId }: { recordId: string }) {
  const [prescriptionModal, setPrescriptionModal] = useState(false)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const isDoctor = useIsDoctor()
  const { data: record, isLoading } = useRecord(recordId)
  const { data: analyses } = useRecordAnalyses(recordId)
  const requestAnalysis = useRequestAnalysis()

  if (isLoading) return <PageLoader />
  if (!record) return (
    <Card>
      <CardBody>
        <EmptyState
          icon={<FileText className="w-7 h-7" />}
          title="Prontuário não encontrado"
          description="O prontuário solicitado não está disponível ou foi removido."
        />
      </CardBody>
    </Card>
  )

  const handleAnalyze = async () => {
    setAnalysisLoading(true)
    try {
      await requestAnalysis.mutateAsync({
        analysis_type: 'SYMPTOM_ANALYSIS',
        patient_id: record.patient_id,
        record_id: record.id,
        context: {
          chief_complaint: record.chief_complaint,
          anamnesis: record.anamnesis,
          diagnosis_codes: record.diagnosis_codes,
        },
      })
    } finally {
      setAnalysisLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Main record */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Stethoscope className="w-4 h-4 text-brand-400" />
                Prontuário — {formatDate(record.created_at)}
              </h3>
              <span className="text-xs text-slate-500 mt-1 block">ID: {record.id}</span>
            </div>
            {isDoctor && (
              <div className="flex gap-2">
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<Brain className="w-3.5 h-3.5" />}
                  loading={analysisLoading}
                  onClick={handleAnalyze}
                >
                  Análise IA
                </Button>
                <Button
                  size="sm"
                  icon={<Pill className="w-3.5 h-3.5" />}
                  onClick={() => setPrescriptionModal(true)}
                >
                  Prescrição
                </Button>
              </div>
            )}
          </div>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {[
              { label: 'Queixa Principal', value: record.chief_complaint },
              { label: 'Diagnóstico', value: record.diagnosis },
              { label: 'Anamnese', value: record.anamnesis, full: true },
              { label: 'Exame Físico', value: record.physical_exam, full: true },
              { label: 'Plano Terapêutico', value: record.treatment_plan, full: true },
              { label: 'Observações', value: record.observations, full: true },
            ].map(({ label, value, full }) => value ? (
              <div key={label} className={cn('space-y-1', full && 'lg:col-span-2')}>
                <dt className="text-xs font-medium text-slate-500 uppercase tracking-wider">{label}</dt>
                <dd className="text-sm text-slate-300 leading-relaxed whitespace-pre-line">{value}</dd>
              </div>
            ) : null)}

            {record.diagnosis_codes.length > 0 && (
              <div className="space-y-1">
                <dt className="text-xs font-medium text-slate-500 uppercase tracking-wider">CID-10</dt>
                <dd className="flex flex-wrap gap-1.5">
                  {record.diagnosis_codes.map((code) => (
                    <Badge key={code} className="bg-slate-700/60 text-slate-300 ring-slate-600/30 font-mono">
                      {code}
                    </Badge>
                  ))}
                </dd>
              </div>
            )}
          </div>
        </CardBody>
      </Card>

      {/* Prescriptions */}
      {record.prescriptions.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Pill className="w-4 h-4 text-violet-400" />
              Prescrições ({record.prescriptions.length})
            </h3>
          </CardHeader>
          <CardBody className="space-y-4">
            {record.prescriptions.map((rx) => (
              <div key={rx.id} className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/60">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-slate-500">{formatDate(rx.created_at)} · Válida por {rx.valid_days} dias</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    icon={<Download className="w-3.5 h-3.5" />}
                    onClick={async () => {
                      try {
                        const response = await recordsApi.downloadPrescription(record.id, rx.id)
                        const contentType = typeof response.headers['content-type'] === 'string'
                          ? response.headers['content-type']
                          : 'application/pdf'
                        const blob = new Blob([response.data], { type: contentType })
                        const url = window.URL.createObjectURL(blob)
                        const a = document.createElement('a')
                        a.href = url
                        a.download = `prescricao-${rx.id.slice(0, 8)}.pdf`
                        a.click()
                        window.URL.revokeObjectURL(url)
                      } catch (err) {
                        const msg = getErrorMessage(err)
                        if (msg.includes('202') || msg.includes('gerado')) {
                          alert('PDF ainda está sendo gerado. Tente novamente em alguns segundos.')
                        } else {
                          alert('Erro ao baixar PDF: ' + msg)
                        }
                      }
                    }}
                  >
                    PDF
                  </Button>
                </div>
                <div className="space-y-2">
                  {rx.medications.map((med, i) => (
                    <div key={i} className="flex items-start gap-3 text-sm">
                      <span className="text-slate-600 text-xs mt-0.5">{i + 1}.</span>
                      <div>
                        <span className="font-medium text-slate-200">{med.name} {med.dosage}</span>
                        <span className="text-slate-500"> — {med.frequency}, {med.duration_days} dias</span>
                      </div>
                    </div>
                  ))}
                </div>
                {rx.instructions && (
                  <p className="text-xs text-slate-500 mt-3 italic">ℹ {rx.instructions}</p>
                )}
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      {/* Exam requests */}
      {record.exam_requests.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-sky-400" />
              Solicitações de Exame ({record.exam_requests.length})
            </h3>
          </CardHeader>
          <Table>
            <thead>
              <tr>
                <Th>Exame</Th>
                <Th>Urgência</Th>
                <Th>Instruções</Th>
                <Th>Resultado</Th>
              </tr>
            </thead>
            <tbody>
              {record.exam_requests.map((exam) => (
                <tr key={exam.id} className="hover:bg-slate-800/20 transition-colors">
                  <Td className="font-medium text-slate-200">{exam.exam_type}</Td>
                  <Td>
                    <Badge className={
                      exam.urgency === 'EMERGENCY' ? 'bg-rose-500/15 text-rose-300 ring-rose-500/20' :
                      exam.urgency === 'URGENT' ? 'bg-amber-500/15 text-amber-300 ring-amber-500/20' :
                      'bg-slate-500/15 text-slate-400 ring-slate-500/20'
                    }>
                      {exam.urgency === 'ROUTINE' ? 'Rotina' : exam.urgency === 'URGENT' ? 'Urgente' : 'Emergência'}
                    </Badge>
                  </Td>
                  <Td>{exam.instructions ?? '—'}</Td>
                  <Td className="max-w-xs">
                    {exam.result ? (
                      <span className="text-emerald-400 text-xs">{exam.result.slice(0, 80)}…</span>
                    ) : (
                      <span className="text-slate-600 text-xs">Aguardando</span>
                    )}
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}

      {/* AI analyses */}
      {analyses && analyses.items.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Brain className="w-4 h-4 text-violet-400" />
              Análises de IA ({analyses.items.length})
            </h3>
          </CardHeader>
          <CardBody className="space-y-3">
            {analyses.items.map((job) => (
              <div key={job.id} className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/60">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-medium text-slate-400">{job.analysis_type.replace(/_/g, ' ')}</span>
                  <div className="flex items-center gap-2">
                    {job.risk_level && (
                      <span className={cn('text-xs font-semibold', RISK_COLORS[job.risk_level])}>
                        Risco: {job.risk_level}
                      </span>
                    )}
                    <Badge className={
                      job.status === 'COMPLETED' ? 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/20' :
                      job.status === 'FAILED' ? 'bg-rose-500/15 text-rose-300 ring-rose-500/20' :
                      'bg-amber-500/15 text-amber-300 ring-amber-500/20'
                    } dot>
                      {job.status === 'PENDING' ? 'Aguardando' : job.status === 'RUNNING' ? 'Processando' :
                       job.status === 'COMPLETED' ? 'Concluído' : 'Falhou'}
                    </Badge>
                  </div>
                </div>
                {job.result && typeof job.result === 'object' && 'recommendations' in job.result && (
                  <div className="mt-2">
                    <p className="text-xs text-slate-500 mb-1">Recomendações:</p>
                    <ul className="space-y-0.5">
                      {(job.result.recommendations as string[]).map((r, i) => (
                        <li key={i} className="text-xs text-slate-400">• {r}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
          </CardBody>
        </Card>
      )}

      <PrescriptionModal
        recordId={record.id}
        open={prescriptionModal}
        onClose={() => setPrescriptionModal(false)}
      />
    </div>
  )
}

export function RecordsPage() {
  const { patientId, recordId } = useParams<{ patientId?: string; recordId?: string }>()
  const [createModal, setCreateModal] = useState(false)
  const isDoctor = useIsDoctor()
  const isPatient = useIsPatient()
  const navigate = useNavigate()
  const { user } = useAuthStore()

  // If viewing a specific record
  if (recordId) {
    return (
      <div>
        <PageHeader
          title="Prontuário"
          breadcrumb={[
            { label: 'Prontuários' },
            { label: 'Detalhes' },
          ]}
          action={
            <Button variant="ghost" icon={<ArrowLeft className="w-4 h-4" />} onClick={() => navigate(-1)}>
              Voltar
            </Button>
          }
        />
        <RecordDetailView recordId={recordId} />
      </div>
    )
  }

  // If viewing records for a patient
  const pid = patientId || (isPatient ? user?.id : '')
  const { data: recordsByPatient, isLoading: loadingPatient } = usePatientRecords(pid || '')
  const { data: allRecords, isLoading: loadingAll } = useRecords()

  const records = pid ? recordsByPatient : allRecords
  const isLoading = pid ? loadingPatient : loadingAll

  return (
    <div>
      <PageHeader
        title="Prontuários"
        description="Histórico clínico completo"
        action={
          isDoctor ? (
            <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateModal(true)}>
              Novo Prontuário
            </Button>
          ) : undefined
        }
      />

      {isLoading ? (
        <PageLoader />
      ) : !records?.items.length ? (
        <Card>
          <CardBody>
            <EmptyState
              icon={<ClipboardList className="w-8 h-8" />}
              title="Nenhum prontuário registrado"
              description="Os prontuários são criados após as consultas e aparecem aqui para revisão clínica."
              action={
                isDoctor ? (
                  <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateModal(true)}>
                    Criar Prontuário
                  </Button>
                ) : undefined
              }
            />
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-3">
          {records.items.map((record) => (
            <RecordCard key={record.id} record={record} />
          ))}
        </div>
      )}

      <CreateRecordModal open={createModal} onClose={() => setCreateModal(false)} />
    </div>
  )
}
