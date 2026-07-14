import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  ArrowLeft, UserRound, Phone, MapPin, Heart,
  Syringe, Pill, Calendar, Plus, Trash2, AlertTriangle, FileText, Eye,
} from 'lucide-react'
import {
  usePatient, usePatientAllergies, usePatientVaccines,
  usePatientMedications, useAddAllergy, useDeleteAllergy,
  useAddVaccine, useAddMedication, useDeleteMedication,
  useAppointments, usePatientRecords,
} from '@/hooks'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Input, Select,
  Badge, PageLoader, EmptyState, Modal, Alert, Table, Th, Td,
} from '@/components/ui'
import {
  formatDate, formatDateTime, calculateAge,
  SEVERITY_COLORS, STATUS_LABELS, STATUS_COLORS, cn, getErrorMessage,
} from '@/utils'
import { useIsDoctor, useIsAdmin, useIsAttendant } from '@/store/auth.store'

type Tab = 'overview' | 'allergies' | 'vaccines' | 'medications' | 'appointments' | 'records'

const medicationSchema = z.object({
  name: z.string().min(2, 'Nome do medicamento obrigatório'),
  dosage: z.string().min(1, 'Dosagem obrigatória'),
  frequency: z.string().min(1, 'Frequência obrigatória'),
  prescribing_doctor: z.string().optional(),
  started_at: z.string().optional(),
  notes: z.string().optional(),
})
type MedicationForm = z.infer<typeof medicationSchema>

function AddMedicationModal({ patientId, open, onClose }: { patientId: string; open: boolean; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const addMedication = useAddMedication()
  const { register, handleSubmit, reset, formState: { errors } } = useForm<MedicationForm>({
    resolver: zodResolver(medicationSchema),
  })

  const onSubmit = async (data: MedicationForm) => {
    setError(null)
    try {
      const payload = {
        ...data,
        prescribing_doctor: data.prescribing_doctor || undefined,
        started_at: data.started_at || undefined,
        notes: data.notes || undefined,
      }
      await addMedication.mutateAsync({ patientId, data: payload })
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Adicionar Medicamento"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={addMedication.isPending}>Salvar</Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        <Input label="Nome do Medicamento *" placeholder="Losartana, Omeprazol…" error={errors.name?.message} {...register('name')} />
        <Input label="Dosagem *" placeholder="50mg, 20mg…" error={errors.dosage?.message} {...register('dosage')} />
        <Input label="Frequência *" placeholder="1x ao dia, 12/12h…" error={errors.frequency?.message} {...register('frequency')} />
        <Input label="Médico Prescritor" placeholder="Dr. Nome" {...register('prescribing_doctor')} />
        <Input label="Data de início" type="date" {...register('started_at')} />
        <Input label="Observações" {...register('notes')} />
      </div>
    </Modal>
  )
}

const vaccineSchema = z.object({
  name: z.string().min(2, 'Nome da vacina obrigatório'),
  dose: z.string().optional(),
  applied_at: z.string().optional(),
  next_dose_at: z.string().optional(),
  notes: z.string().optional(),
})
type VaccineForm = z.infer<typeof vaccineSchema>

function AddVaccineModal({ patientId, open, onClose }: { patientId: string; open: boolean; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const addVaccine = useAddVaccine()
  const { register, handleSubmit, reset, formState: { errors } } = useForm<VaccineForm>({
    resolver: zodResolver(vaccineSchema),
  })

  const onSubmit = async (data: VaccineForm) => {
    setError(null)
    try {
      const payload = {
        ...data,
        dose: data.dose || undefined,
        applied_at: data.applied_at || undefined,
        next_dose_at: data.next_dose_at || undefined,
        notes: data.notes || undefined,
      }
      await addVaccine.mutateAsync({ patientId, data: payload })
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Adicionar Vacina"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={addVaccine.isPending}>Salvar</Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        <Input label="Nome da Vacina *" placeholder="BCG, Hepatite B…" error={errors.name?.message} {...register('name')} />
        <Input label="Dose" placeholder="1ª dose, 2ª dose…" {...register('dose')} />
        <Input label="Data de aplicação" type="date" {...register('applied_at')} />
        <Input label="Próxima dose" type="date" {...register('next_dose_at')} />
        <Input label="Observações" {...register('notes')} />
      </div>
    </Modal>
  )
}

const allergySchema = z.object({
  substance: z.string().min(2, 'Substância obrigatória'),
  severity: z.enum(['MILD', 'MODERATE', 'SEVERE']),
  reaction_type: z.string().optional(),
  notes: z.string().optional(),
})
type AllergyForm = z.infer<typeof allergySchema>

function AddAllergyModal({ patientId, open, onClose }: { patientId: string; open: boolean; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const addAllergy = useAddAllergy()
  const { register, handleSubmit, reset, formState: { errors } } = useForm<AllergyForm>({
    resolver: zodResolver(allergySchema),
    defaultValues: { severity: 'MODERATE' },
  })

  const onSubmit = async (data: AllergyForm) => {
    setError(null)
    try {
      const payload = {
        ...data,
        reaction_type: data.reaction_type || undefined,
        notes: data.notes || undefined,
      }
      await addAllergy.mutateAsync({ patientId, data: payload })
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Adicionar Alergia"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={addAllergy.isPending}>Salvar</Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        <Input label="Substância *" placeholder="Penicilina" error={errors.substance?.message} {...register('substance')} />
        <Select
          label="Gravidade *"
          options={[
            { value: 'MILD', label: 'Leve' },
            { value: 'MODERATE', label: 'Moderada' },
            { value: 'SEVERE', label: 'Grave' },
          ]}
          error={errors.severity?.message}
          {...register('severity')}
        />
        <Input label="Tipo de reação" placeholder="Anafilaxia, urticária…" {...register('reaction_type')} />
        <Input label="Observações" {...register('notes')} />
      </div>
    </Modal>
  )
}

function InfoRow({ label, value, className }: { label: string; value?: string | null; className?: string }) {
  return (
    <div className={cn('flex flex-col gap-0.5', className)}>
      <dt className="text-xs text-slate-500 font-medium">{label}</dt>
      <dd className="text-sm text-slate-200">{value ?? '—'}</dd>
    </div>
  )
}

export function PatientDetailPage() {
  const { id = '' } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [tab, setTab] = useState<Tab>('overview')
  const [allergyModal, setAllergyModal] = useState(false)
  const [vaccineModal, setVaccineModal] = useState(false)
  const [medicationModal, setMedicationModal] = useState(false)
  const canEdit = useIsDoctor() || useIsAdmin() || useIsAttendant()

  const { data: patient, isLoading } = usePatient(id)
  const { data: allergies } = usePatientAllergies(id)
  const { data: vaccines } = usePatientVaccines(id)
  const { data: medications } = usePatientMedications(id)
  const { data: appointments } = useAppointments({ patient_id: id, page: 1, size: 10 })
  const { data: records } = usePatientRecords(id)
  const deleteAllergy = useDeleteAllergy()
  const deleteMedication = useDeleteMedication()

  if (isLoading) return <PageLoader />
  if (!patient) return <div className="text-slate-400 p-6">Paciente não encontrado</div>

  const age = calculateAge(patient.date_of_birth)

  const tabs: { key: Tab; label: string; icon: React.ReactNode; count?: number }[] = [
    { key: 'overview', label: 'Visão Geral', icon: <UserRound className="w-3.5 h-3.5" /> },
    { key: 'allergies', label: 'Alergias', icon: <AlertTriangle className="w-3.5 h-3.5" />, count: allergies?.length },
    { key: 'vaccines', label: 'Vacinas', icon: <Syringe className="w-3.5 h-3.5" />, count: vaccines?.length },
    { key: 'medications', label: 'Medicamentos', icon: <Pill className="w-3.5 h-3.5" />, count: medications?.length },
    { key: 'appointments', label: 'Consultas', icon: <Calendar className="w-3.5 h-3.5" />, count: appointments?.total },
    { key: 'records', label: 'Prontuários', icon: <FileText className="w-3.5 h-3.5" />, count: records?.items?.length },
  ]

  return (
    <div>
      <PageHeader
        title={patient.full_name}
        description={age !== null ? `${age} anos · ${patient.blood_type ?? 'Tipo sang. não informado'}` : patient.blood_type ?? ''}
        breadcrumb={[{ label: 'Pacientes', href: '/patients' }, { label: patient.full_name }]}
        action={
          <Button variant="ghost" icon={<ArrowLeft className="w-4 h-4" />} onClick={() => navigate('/patients')}>
            Voltar
          </Button>
        }
      />

      {/* Header card */}
      <Card className="mb-6">
        <CardBody className="flex flex-wrap items-center gap-6">
          <div className="w-16 h-16 rounded-2xl bg-brand-500/15 border border-brand-500/20 flex items-center justify-center flex-shrink-0">
            <UserRound className="w-8 h-8 text-brand-400" />
          </div>
          <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4">
            <InfoRow label="CPF" value={patient.cpf} />
            <InfoRow label="Data de Nascimento" value={formatDate(patient.date_of_birth)} />
            <InfoRow label="Gênero" value={patient.gender === 'M' ? 'Masculino' : patient.gender === 'F' ? 'Feminino' : patient.gender ?? undefined} />
            <InfoRow label="Tipo Sanguíneo" value={patient.blood_type} />
            <InfoRow label="ID (Identificador)" value={patient.id} className="col-span-2 sm:col-span-4" />
          </div>
          <div className="flex gap-2">
            {allergies && allergies.length > 0 && (
              <Badge className="bg-rose-500/15 text-rose-300 ring-rose-500/20" dot>
                {allergies.length} alergia{allergies.length !== 1 ? 's' : ''}
              </Badge>
            )}
            <Badge className={patient.is_active
              ? 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/20'
              : 'bg-slate-500/15 text-slate-400 ring-slate-500/20'
            }>
              {patient.is_active ? 'Ativo' : 'Inativo'}
            </Badge>
          </div>
        </CardBody>
      </Card>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-slate-900/40 p-1 rounded-xl border border-slate-800/60 overflow-x-auto">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all whitespace-nowrap',
              tab === t.key
                ? 'bg-brand-500/15 text-brand-300 shadow-sm'
                : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/40'
            )}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span className="px-1.5 py-0.5 bg-slate-700/60 rounded text-[10px] text-slate-400">
                {t.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader><h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Phone className="w-4 h-4 text-brand-400" />Contato</h3></CardHeader>
            <CardBody>
              <dl className="grid grid-cols-2 gap-4">
                <InfoRow label="Telefone" value={patient.phone} />
                <InfoRow label="Email" value={patient.email} />
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader><h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><MapPin className="w-4 h-4 text-brand-400" />Endereço</h3></CardHeader>
            <CardBody>
              <dl className="grid grid-cols-2 gap-4">
                <InfoRow label="Rua" value={patient.street} className="col-span-2" />
                <InfoRow label="Cidade" value={patient.city} />
                <InfoRow label="Estado" value={patient.state} />
                <InfoRow label="CEP" value={patient.zip_code} />
              </dl>
            </CardBody>
          </Card>

          <Card className="lg:col-span-2">
            <CardHeader><h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Heart className="w-4 h-4 text-rose-400" />Contato de Emergência</h3></CardHeader>
            <CardBody>
              <dl className="grid grid-cols-3 gap-4">
                <InfoRow label="Nome" value={patient.emergency_name} />
                <InfoRow label="Telefone" value={patient.emergency_phone} />
                <InfoRow label="Parentesco" value={patient.emergency_relation} />
              </dl>
            </CardBody>
          </Card>

          {patient.notes && (
            <Card className="lg:col-span-2">
              <CardHeader><h3 className="text-sm font-semibold text-slate-200">Observações</h3></CardHeader>
              <CardBody><p className="text-sm text-slate-400">{patient.notes}</p></CardBody>
            </Card>
          )}
        </div>
      )}

      {tab === 'allergies' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-200">Alergias Registradas</h3>
              {canEdit && (
                <Button size="sm" icon={<Plus className="w-3.5 h-3.5" />} onClick={() => setAllergyModal(true)}>
                  Adicionar
                </Button>
              )}
            </div>
          </CardHeader>
          {!allergies?.length ? (
            <CardBody>
              <EmptyState
                icon={<AlertTriangle className="w-7 h-7" />}
                title="Nenhuma alergia registrada"
                action={canEdit ? (
                  <Button size="sm" icon={<Plus className="w-3.5 h-3.5" />} onClick={() => setAllergyModal(true)}>
                    Adicionar Alergia
                  </Button>
                ) : undefined}
              />
            </CardBody>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Substância</Th>
                  <Th>Gravidade</Th>
                  <Th>Tipo de Reação</Th>
                  <Th>Registrado em</Th>
                  {canEdit && <Th>Ações</Th>}
                </tr>
              </thead>
              <tbody>
                {allergies.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-800/20 transition-colors">
                    <Td className="font-medium text-slate-200">{a.substance}</Td>
                    <Td>
                      <Badge className={SEVERITY_COLORS[a.severity]}>
                        {a.severity === 'MILD' ? 'Leve' : a.severity === 'MODERATE' ? 'Moderada' : 'Grave'}
                      </Badge>
                    </Td>
                    <Td>{a.reaction_type ?? '—'}</Td>
                    <Td>{formatDate(a.created_at)}</Td>
                    {canEdit && (
                      <Td>
                        <button
                          onClick={() => deleteAllergy.mutate({ patientId: id, allergyId: a.id })}
                          className="p-1.5 rounded-lg text-slate-600 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </Td>
                    )}
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}

      {tab === 'vaccines' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-200">Cartão de Vacinação</h3>
              {canEdit && (
                <Button size="sm" icon={<Plus className="w-3.5 h-3.5" />} onClick={() => setVaccineModal(true)}>
                  Adicionar
                </Button>
              )}
            </div>
          </CardHeader>
          {!vaccines?.length ? (
            <CardBody>
              <EmptyState
                icon={<Syringe className="w-7 h-7" />}
                title="Nenhuma vacina registrada"
                action={canEdit ? (
                  <Button size="sm" icon={<Plus className="w-3.5 h-3.5" />} onClick={() => setVaccineModal(true)}>
                    Adicionar Vacina
                  </Button>
                ) : undefined}
              />
            </CardBody>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Vacina</Th>
                  <Th>Dose</Th>
                  <Th>Aplicada em</Th>
                  <Th>Próxima dose</Th>
                </tr>
              </thead>
              <tbody>
                {vaccines.map((v) => (
                  <tr key={v.id} className="hover:bg-slate-800/20 transition-colors">
                    <Td className="font-medium text-slate-200">{v.name}</Td>
                    <Td>{v.dose ?? '—'}</Td>
                    <Td>{formatDate(v.applied_at)}</Td>
                    <Td>{formatDate(v.next_dose_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}

      {tab === 'medications' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-200">Medicamentos Contínuos</h3>
              {canEdit && (
                <Button size="sm" icon={<Plus className="w-3.5 h-3.5" />} onClick={() => setMedicationModal(true)}>
                  Adicionar
                </Button>
              )}
            </div>
          </CardHeader>
          {!medications?.length ? (
            <CardBody>
              <EmptyState
                icon={<Pill className="w-7 h-7" />}
                title="Nenhum medicamento contínuo"
                action={canEdit ? (
                  <Button size="sm" icon={<Plus className="w-3.5 h-3.5" />} onClick={() => setMedicationModal(true)}>
                    Adicionar Medicamento
                  </Button>
                ) : undefined}
              />
            </CardBody>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Medicamento</Th>
                  <Th>Dosagem</Th>
                  <Th>Frequência</Th>
                  <Th>Médico Prescritor</Th>
                  <Th>Desde</Th>
                  {canEdit && <Th>Ações</Th>}
                </tr>
              </thead>
              <tbody>
                {medications.map((m) => (
                  <tr key={m.id} className="hover:bg-slate-800/20 transition-colors">
                    <Td className="font-medium text-slate-200">{m.name}</Td>
                    <Td>{m.dosage}</Td>
                    <Td>{m.frequency}</Td>
                    <Td>{m.prescribing_doctor ?? '—'}</Td>
                    <Td>{formatDate(m.started_at)}</Td>
                    {canEdit && (
                      <Td>
                        <button
                          onClick={() => {
                            if (confirm('Remover este medicamento permanentemente?')) {
                              deleteMedication.mutate({ patientId: id, medId: m.id })
                            }
                          }}
                          className="p-1.5 rounded-lg text-slate-600 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </Td>
                    )}
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}

      {tab === 'appointments' && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-200">Histórico de Consultas</h3>
            </div>
          </CardHeader>
          {!appointments?.items.length ? (
            <CardBody>
              <EmptyState icon={<Calendar className="w-7 h-7" />} title="Nenhuma consulta registrada" />
            </CardBody>
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Data</Th>
                  <Th>Tipo</Th>
                  <Th>Especialidade</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {appointments.items.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-800/20 transition-colors">
                    <Td>{formatDateTime(a.scheduled_at)}</Td>
                    <Td>{a.appointment_type}</Td>
                    <Td>{a.specialty ?? '—'}</Td>
                    <Td>
                      <Badge className={STATUS_COLORS[a.status]}>
                        {STATUS_LABELS[a.status]}
                      </Badge>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}

      {tab === 'records' && (
        <Card className="mt-6 border-slate-700/50">
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-200">Prontuários do Paciente</h3>
          </CardHeader>
          {!records?.items || records.items.length === 0 ? (
            <EmptyState
              title="Nenhum prontuário"
              description="O paciente ainda não possui prontuários registrados."
              icon={<FileText className="w-12 h-12 text-slate-600" />}
            />
          ) : (
            <Table>
              <thead>
                <tr>
                  <Th>Data</Th>
                  <Th>Queixa Principal</Th>
                  <Th>Diagnóstico</Th>
                  <Th>Ações</Th>
                </tr>
              </thead>
              <tbody>
                {records.items.map((r) => (
                  <tr key={r.id} className="hover:bg-slate-800/20 transition-colors">
                    <Td>{formatDateTime(r.created_at)}</Td>
                    <Td className="truncate max-w-[200px]">{r.chief_complaint}</Td>
                    <Td className="truncate max-w-[200px]">{r.diagnosis || '—'}</Td>
                    <Td>
                      <Button
                        variant="ghost"
                        size="sm"
                        icon={<Eye className="w-4 h-4 text-slate-400" />}
                        onClick={() => navigate(`/records/${r.id}`)}
                      >
                        Visualizar
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Card>
      )}

      <AddAllergyModal
        patientId={id}
        open={allergyModal}
        onClose={() => setAllergyModal(false)}
      />
      <AddVaccineModal
        patientId={id}
        open={vaccineModal}
        onClose={() => setVaccineModal(false)}
      />
      <AddMedicationModal
        patientId={id}
        open={medicationModal}
        onClose={() => setMedicationModal(false)}
      />
    </div>
  )
}
