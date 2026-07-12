import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useQueryClient } from '@tanstack/react-query'
import { UserRound, Search, Plus, Eye, ChevronRight } from 'lucide-react'
import { usePatients, keys } from '@/hooks'
import { usersApi, patientsApi } from '@/api/services'
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
  // User fields
  email: z.string().email('Email inválido'),
  password: z
    .string()
    .min(8, 'Mínimo 8 caracteres')
    .regex(/[A-Z]/, 'Deve conter ao menos uma letra maiúscula')
    .regex(/[0-9]/, 'Deve conter ao menos um número'),
  full_name: z.string().min(2, 'Nome obrigatório'),
  // Patient fields
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
  const [isLoading, setIsLoading] = useState(false)
  const queryClient = useQueryClient()

  const { register, handleSubmit, reset, formState: { errors } } = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
  })

  const onSubmit = async (data: CreateForm) => {
    setError(null)
    setIsLoading(true)
    try {
      // Step 1: Create user with role PATIENT
      const user = await usersApi.create({
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        role: 'PATIENT',
      })

      // Step 2: Create patient linked to the user
      await patientsApi.create({
        user_id: user.id,
        full_name: data.full_name,
        cpf: data.cpf || undefined,
        date_of_birth: data.date_of_birth || undefined,
        gender: data.gender,
        blood_type: data.blood_type || undefined,
        phone: data.phone || undefined,
      })

      // Invalidate patients list cache to refresh the table
      queryClient.invalidateQueries({ queryKey: keys.patients.all })

      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }

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
            loading={isLoading}
          >
            Cadastrar
          </Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-5">{error}</Alert>}
      <div className="space-y-5">
        {/* User credentials */}
        <div>
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Credenciais de Acesso
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="sm:col-span-2">
              <Input
                label="Nome completo *"
                placeholder="João da Silva"
                error={errors.full_name?.message}
                {...register('full_name')}
              />
            </div>
            <Input
              label="Email *"
              type="email"
              placeholder="paciente@email.com"
              error={errors.email?.message}
              {...register('email')}
            />
            <Input
              label="Senha *"
              type="password"
              placeholder="Mín. 8 caracteres, 1 maiúscula, 1 número"
              error={errors.password?.message}
              {...register('password')}
            />
          </div>
        </div>

        {/* Patient data */}
        <div className="pt-4 border-t border-slate-800/60">
          <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">
            Dados do Paciente
          </h4>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
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
  const queryClient = useQueryClient()

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

  const handleCreateClose = () => {
    setCreateOpen(false)
    // Invalidate all patient queries to force refetch
    queryClient.invalidateQueries({ queryKey: ['patients'] })
  }

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
                  <Th>Ações</Th>
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
        onClose={handleCreateClose}
      />
    </div>
  )
}