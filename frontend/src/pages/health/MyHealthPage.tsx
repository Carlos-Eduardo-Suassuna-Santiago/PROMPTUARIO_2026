import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AlertTriangle, Syringe, Plus, Trash2, Pill } from 'lucide-react'
import { 
  useMyPatient, usePatientAllergies, usePatientVaccines, 
  useAddAllergy, useDeleteAllergy, usePatientMedications
} from '@/hooks'
import { useIsPatient } from '@/store/auth.store'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Input, Alert, Select,
  Modal, Table, Th, Td, Badge, EmptyState, PageLoader
} from '@/components/ui'
import { formatDate, getErrorMessage } from '@/utils'
import { Navigate } from 'react-router-dom'

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
      await addAllergy.mutateAsync({ patientId, data })
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
        <Input label="Tipo de reação" placeholder="Manchas, falta de ar..." {...register('reaction_type')} />
        <Input label="Observações" {...register('notes')} />
      </div>
    </Modal>
  )
}

export function MyHealthPage() {
  const isPatient = useIsPatient()
  const { data: patient, isLoading: patientLoading } = useMyPatient()
  const [allergyModal, setAllergyModal] = useState(false)

  const { data: allergies } = usePatientAllergies(patient?.id || '')
  const { data: vaccines } = usePatientVaccines(patient?.id || '')
  const { data: medications } = usePatientMedications(patient?.id || '')
  const deleteAllergy = useDeleteAllergy()

  if (!isPatient) {
    return <Navigate to="/dashboard" replace />
  }

  if (patientLoading) return <PageLoader />

  return (
    <div>
      <PageHeader
        title="Minha Saúde"
        description="Acompanhe seu cartão de vacinação, histórico de medicamentos e registre suas alergias"
      />

      <div className="grid grid-cols-1 gap-6 max-w-4xl mx-auto mt-6">
        {patient && (
          <>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-brand-400" />
                    Alergias Registradas
                  </h3>
                  <Button size="sm" icon={<Plus className="w-3.5 h-3.5" />} onClick={() => setAllergyModal(true)}>
                    Adicionar
                  </Button>
                </div>
              </CardHeader>
              {!allergies?.length ? (
                <CardBody>
                  <EmptyState
                    icon={<AlertTriangle className="w-7 h-7" />}
                    title="Nenhuma alergia registrada"
                    action={
                      <Button size="sm" icon={<Plus className="w-3.5 h-3.5" />} onClick={() => setAllergyModal(true)}>
                        Adicionar Alergia
                      </Button>
                    }
                  />
                </CardBody>
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>Substância</Th>
                      <Th>Gravidade</Th>
                      <Th>Reação</Th>
                      <Th>Data do Registro</Th>
                      <Th></Th>
                    </tr>
                  </thead>
                  <tbody>
                    {allergies.map((a) => (
                      <tr key={a.id} className="hover:bg-slate-800/20 transition-colors">
                        <Td className="font-medium text-slate-200">{a.substance}</Td>
                        <Td>
                          <Badge className={a.severity === 'SEVERE' ? 'bg-rose-500/15 text-rose-300' : 'bg-amber-500/15 text-amber-300'}>
                            {a.severity === 'MILD' ? 'Leve' : a.severity === 'MODERATE' ? 'Moderada' : 'Grave'}
                          </Badge>
                        </Td>
                        <Td>{a.reaction_type ?? '—'}</Td>
                        <Td>{formatDate(a.created_at)}</Td>
                        <Td>
                          <button
                            onClick={() => deleteAllergy.mutate({ patientId: patient.id, allergyId: a.id })}
                            className="p-1.5 rounded-lg text-slate-600 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                            title="Remover alergia"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <Syringe className="w-4 h-4 text-brand-400" />
                    Cartão de Vacinação
                  </h3>
                </div>
              </CardHeader>
              {!vaccines?.length ? (
                <CardBody>
                  <EmptyState
                    icon={<Syringe className="w-7 h-7" />}
                    title="Nenhuma vacina registrada"
                  />
                </CardBody>
              ) : (
                <Table>
                  <thead>
                    <tr>
                      <Th>Vacina</Th>
                      <Th>Dose</Th>
                      <Th>Aplicação</Th>
                      <Th>Próxima Dose</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {vaccines.map((v) => (
                      <tr key={v.id} className="hover:bg-slate-800/20 transition-colors">
                        <Td className="font-medium text-slate-200">{v.name}</Td>
                        <Td>{v.dose ?? '—'}</Td>
                        <Td>{v.applied_at ? formatDate(v.applied_at) : '—'}</Td>
                        <Td>{v.next_dose_at ? formatDate(v.next_dose_at) : '—'}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                    <Pill className="w-4 h-4 text-brand-400" />
                    Medicamentos em Uso
                  </h3>
                </div>
              </CardHeader>
              {!medications?.length ? (
                <CardBody>
                  <EmptyState
                    icon={<Pill className="w-7 h-7" />}
                    title="Nenhum medicamento registrado"
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
                      </tr>
                    ))}
                  </tbody>
                </Table>
              )}
            </Card>

            <AddAllergyModal
              patientId={patient.id}
              open={allergyModal}
              onClose={() => setAllergyModal(false)}
            />
          </>
        )}
      </div>
    </div>
  )
}
