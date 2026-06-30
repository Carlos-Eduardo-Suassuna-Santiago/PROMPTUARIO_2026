import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { UserRound, Search, Plus, Eye, ChevronRight } from 'lucide-react'
import { usePatients, useUsers, useCreatePatient } from '@/hooks'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Input, Select, Modal,
  Table, Th, Td, Badge, PageLoader, EmptyState, Pagination,
  Alert,
} from '@/components/ui'
import { formatDate, calculateAge, cn, getErrorMessage } from '@/utils'
import type { Patient } from '@/types'

// ─── Create Patient Modal ─────────────────────────────────────────────────
const createSchema = z.object({
  user_id: z.string().min(1, 'Selecione um usuário'),
  full_name: z.string().min(2, 'Nome obrigatório'),
  cpf: z.string().regex(/^\d{3}\.\d{3}\.\d{3}-\d{2}$/, 'CPF inválido (000.000.000-00)').optional().or(z.literal('')),
  date_of_birth: z.string().optional(),
  gender: z.enum(['M', 'F', 'OTHER']).optional(),
  blood_type: z.string().optional(),
  phone: z.string().optional(),
})

type CreateForm = z.infer<typeof createSchema>

function CreatePatientModal({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const [error, setError] = useState<string | null>(null)
  const { data: users } = useUsers({ role: 'PATIENT', is_active: true, size: 100 })
  const createPatient = useCreatePatient()

  const { register, handleSubmit, reset, formState: { errors } } = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
  })

  const onSubmit = async (data: CreateForm) => {
    setError(null)
    try {
      await createPatient.mutateAsync({
        user_id: data.user_id,
        full_name: data.full_name,
        cpf: data.cpf || undefined,
        date_of_birth: data.date_of_birth || undefined,
        gender: data.gender,
        blood_type: data.blood_type || undefined,
        phone: data.phone || undefined,
      })
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  const userOptions = users?.items.map((u) => ({ value: u.id, label: `${u.full_name} — ${u.email}` })) ?? []

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Cadastrar Paciente"
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button
            onClick={handleSubmit(onSubmit)}
            loading={createPatient.isPending}
          >
            Cadastrar
          </Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-5">{error}</Alert>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <div className="sm:col-span-2">
          <Select
            label="Usuário do sistema *"
            options={userOptions}
            placeholder="Selecione o usuário paciente"
            error={errors.user_id?.message}
            {...register('user_id')}
          />
        </div>
        <div className="sm:col-span-2">
          <Input
            label="Nome completo *"
            placeholder="João da Silva"
            error={errors.full_name?.message}
            {...register('full_name')}
          />
        </div>
        <Input
          label="CPF"
          placeholder="000.000.000-00"
          error={errors.cpf?.message}
          {...register('cpf')}
        />
        <Input
          label="Data de nascimento"
          type="date"
          error={errors.date_of_birth?.message}
          {...register('date_of_birth')}
        />
        <Select
          label="Gênero"
          options={[
            { value: 'M', label: 'Masculino' },
            { value: 'F', label: 'Feminino' },
            { value: 'OTHER', label: 'Outro' },
          ]}
          placeholder="Selecione"
          {...register('gender')}
        />
        <Input
          label="Tipo sanguíneo"
          placeholder="O+"
          {...register('blood_type')}
        />
        <div className="sm:col-span-2">
          <Input
            label="Telefone"
            placeholder="+55 84 99999-0000"
            {...register('phone')}
          />
        </div>
      </div>
    </Modal>
  )
}

// ─── Patient Row ─────────────────────────────────────────────────────────
function PatientRow({ patient }: { patient: Patient }) {
  const navigate = useNavigate()
  const age = calculateAge(patient.date_of_birth)

  return (
    <tr
      className="hover:bg-slate-800/30 cursor-pointer transition-colors"
      onClick={() => navigate(`/patients/${patient.id}`)}
    >
      <Td>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-brand-500/15 border border-brand-500/20 flex items-center justify-center flex-shrink-0">
            <UserRound className="w-4 h-4 text-brand-400" />
          </div>
          <div>
            <p className="font-medium text-slate-200">{patient.full_name}</p>
            <p className="text-xs text-slate-500">{patient.email ?? '—'}</p>
          </div>
        </div>
      </Td>
      <Td>
        <span className="font-mono text-xs text-slate-400">{patient.cpf ?? '—'}</span>
      </Td>
      <Td>
        {age !== null ? (
          <span>{age} anos</span>
        ) : (
          <span className="text-slate-600">—</span>
        )}
      </Td>
      <Td>{patient.blood_type ?? <span className="text-slate-600">—</span>}</Td>
      <Td>{patient.phone ?? <span className="text-slate-600">—</span>}</Td>
      <Td>
        <Badge className={patient.is_active
          ? 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/20'
          : 'bg-slate-500/15 text-slate-400 ring-slate-500/20'
        }>
          {patient.is_active ? 'Ativo' : 'Inativo'}
        </Badge>
      </Td>
      <Td>
        <ChevronRight className="w-4 h-4 text-slate-600" />
      </Td>
    </tr>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────
export function PatientListPage() {
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)

  // Debounce search
  const handleSearch = (value: string) => {
    setSearch(value)
    clearTimeout((window as any)._searchTimer)
    ;(window as any)._searchTimer = setTimeout(() => {
      setDebouncedSearch(value)
      setPage(1)
    }, 350)
  }

  const { data, isLoading } = usePatients({
    page,
    size: 20,
    search: debouncedSearch || undefined,
  })

  return (
    <div>
      <PageHeader
        title="Pacientes"
        description={`${data?.total ?? 0} pacientes cadastrados`}
        action={
          <Button
            icon={<Plus className="w-4 h-4" />}
            onClick={() => setCreateOpen(true)}
          >
            Novo Paciente
          </Button>
        }
      />

      <Card>
        <CardHeader>
          <Input
            placeholder="Buscar por nome, CPF ou email…"
            icon={<Search className="w-4 h-4" />}
            value={search}
            onChange={(e) => handleSearch(e.target.value)}
            className="max-w-sm"
          />
        </CardHeader>

        {isLoading ? (
          <PageLoader />
        ) : !data?.items.length ? (
          <CardBody>
            <EmptyState
              icon={<UserRound className="w-8 h-8" />}
              title="Nenhum paciente encontrado"
              description={debouncedSearch ? 'Tente outro termo de busca' : 'Cadastre o primeiro paciente'}
              action={
                !debouncedSearch ? (
                  <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>
                    Cadastrar Paciente
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
                  <Th>Paciente</Th>
                  <Th>CPF</Th>
                  <Th>Idade</Th>
                  <Th>Tipo Sang.</Th>
                  <Th>Telefone</Th>
                  <Th>Status</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {data.items.map((p) => (
                  <PatientRow key={p.id} patient={p} />
                ))}
              </tbody>
            </Table>

            <Pagination
              page={page}
              total={data.total}
              size={20}
              onChange={setPage}
            />
          </>
        )}
      </Card>

      <CreatePatientModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
      />
    </div>
  )
}
