import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Shield, Plus, UserX, Edit2, RefreshCw, Search } from 'lucide-react'
import { useUsers, useCreateUser, useDeactivateUser } from '@/hooks'
import { usersApi } from '@/api/services'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Input, Select, Modal,
  Table, Th, Td, Badge, PageLoader, EmptyState, Pagination,
  Alert,
} from '@/components/ui'
import {
  formatDateTime, ROLE_LABELS, ROLE_COLORS, getErrorMessage, initials,
} from '@/utils'
import type { User, Role } from '@/types'
import { useAuthStore } from '@/store/auth.store'

// ─── Create User Modal ────────────────────────────────────────────────────
const createSchema = z.object({
  email: z.string().email('Email inválido'),
  password: z.string().min(8, 'Mínimo 8 caracteres')
    .regex(/[A-Z]/, 'Precisa de 1 maiúscula')
    .regex(/[0-9]/, 'Precisa de 1 número'),
  full_name: z.string().min(2, 'Nome obrigatório'),
  role: z.enum(['ADMIN', 'DOCTOR', 'ATTENDANT', 'PATIENT'] as const),
})
type CreateForm = z.infer<typeof createSchema>

function CreateUserModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const createUser = useCreateUser()

  const { register, handleSubmit, reset, formState: { errors } } = useForm<CreateForm>({
    resolver: zodResolver(createSchema),
    defaultValues: { role: 'PATIENT' },
  })

  const onSubmit = async (data: CreateForm) => {
    setError(null)
    try {
      await createUser.mutateAsync(data)
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
      title="Criar Usuário"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={createUser.isPending}>Criar</Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        <Input
          label="Nome completo *"
          placeholder="João da Silva"
          error={errors.full_name?.message}
          {...register('full_name')}
        />
        <Input
          label="Email *"
          type="email"
          placeholder="usuario@email.com"
          error={errors.email?.message}
          {...register('email')}
        />
        <Input
          label="Senha *"
          type="password"
          placeholder="Mín. 8 chars, 1 maiúscula, 1 número"
          error={errors.password?.message}
          {...register('password')}
        />
        <Select
          label="Role *"
          options={Object.entries(ROLE_LABELS).map(([v, l]) => ({ value: v, label: l }))}
          error={errors.role?.message}
          {...register('role')}
        />
      </div>
    </Modal>
  )
}

// ─── Deactivate Modal ─────────────────────────────────────────────────────
function DeactivateModal({
  user,
  open,
  onClose,
}: {
  user: User | null
  open: boolean
  onClose: () => void
}) {
  const [reason, setReason] = useState('')
  const [error, setError] = useState<string | null>(null)
  const deactivate = useDeactivateUser()

  const handleConfirm = async () => {
    if (!user || reason.trim().length < 5) return
    setError(null)
    try {
      await deactivate.mutateAsync({ id: user.id, reason })
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
      title="Desativar Usuário"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button
            variant="danger"
            onClick={handleConfirm}
            loading={deactivate.isPending}
            disabled={reason.trim().length < 5}
          >
            Desativar
          </Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <Alert variant="warning" className="mb-4">
        ⚠ O usuário perderá acesso imediatamente. Consultas futuras serão canceladas automaticamente.
      </Alert>
      {user && (
        <div className="flex items-center gap-3 p-3 bg-slate-950/60 rounded-xl border border-slate-800 mb-4">
          <div className="w-8 h-8 rounded-full bg-brand-500/20 flex items-center justify-center">
            <span className="text-xs font-bold text-brand-300">{initials(user.full_name)}</span>
          </div>
          <div>
            <p className="text-sm font-medium text-slate-200">{user.full_name}</p>
            <p className="text-xs text-slate-500">{user.email}</p>
          </div>
        </div>
      )}
      <Input
        label="Motivo *"
        placeholder="Descreva o motivo da desativação…"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
      />
    </Modal>
  )
}

// ─── Edit Role Modal ──────────────────────────────────────────────────────
function EditRoleModal({
  user,
  open,
  onClose,
}: {
  user: User | null
  open: boolean
  onClose: () => void
}) {
  const [role, setRole] = useState<Role>('PATIENT')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { invalidateUsers } = { invalidateUsers: () => {} } // handled via refetch

  const handleSave = async () => {
    if (!user) return
    setLoading(true)
    setError(null)
    try {
      await usersApi.assignRole(user.id, role)
      onClose()
      window.location.reload() // simple invalidation
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Alterar Role"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button onClick={handleSave} loading={loading}>Salvar</Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <Select
        label="Novo Role"
        value={role}
        onChange={(e) => setRole(e.target.value as Role)}
        options={Object.entries(ROLE_LABELS).map(([v, l]) => ({ value: v, label: l }))}
      />
    </Modal>
  )
}

// ─── User Row ─────────────────────────────────────────────────────────────
function UserRow({
  user,
  currentUserId,
  onDeactivate,
  onEditRole,
}: {
  user: User
  currentUserId: string
  onDeactivate: (u: User) => void
  onEditRole: (u: User) => void
}) {
  const isSelf = user.id === currentUserId

  return (
    <tr className="hover:bg-slate-800/20 transition-colors">
      <Td>
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-bold text-slate-300">{initials(user.full_name)}</span>
          </div>
          <div>
            <p className="font-medium text-slate-200">
              {user.full_name}
              {isSelf && (
                <span className="ml-2 text-[10px] text-brand-400 bg-brand-500/10 px-1.5 py-0.5 rounded">você</span>
              )}
            </p>
            <p className="text-xs text-slate-500">{user.email}</p>
          </div>
        </div>
      </Td>
      <Td>
        <Badge className={ROLE_COLORS[user.role]}>
          {ROLE_LABELS[user.role]}
        </Badge>
      </Td>
      <Td>
        <Badge className={user.is_active
          ? 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/20'
          : 'bg-slate-500/15 text-slate-400 ring-slate-500/20'
        } dot>
          {user.is_active ? 'Ativo' : 'Inativo'}
        </Badge>
      </Td>
      <Td className="text-slate-500 text-xs">{formatDateTime(user.created_at)}</Td>
      <Td>
        <div className="flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            icon={<Edit2 className="w-3.5 h-3.5" />}
            onClick={() => onEditRole(user)}
            disabled={isSelf}
          >
            Role
          </Button>
          {user.is_active && !isSelf && (
            <Button
              size="sm"
              variant="danger"
              icon={<UserX className="w-3.5 h-3.5" />}
              onClick={() => onDeactivate(user)}
            >
              Desativar
            </Button>
          )}
        </div>
      </Td>
    </tr>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────
export function UserManagementPage() {
  const [page, setPage] = useState(1)
  const [roleFilter, setRoleFilter] = useState('')
  const [search, setSearch] = useState('')
  const [createOpen, setCreateOpen] = useState(false)
  const [deactivateTarget, setDeactivateTarget] = useState<User | null>(null)
  const [editRoleTarget, setEditRoleTarget] = useState<User | null>(null)

  const { user: currentUser } = useAuthStore()

  const { data, isLoading, refetch } = useUsers({
    page,
    size: 20,
    role: roleFilter || undefined,
  })

  const filteredItems = search
    ? (data?.items ?? []).filter((u) =>
        u.full_name.toLowerCase().includes(search.toLowerCase()) ||
        u.email.toLowerCase().includes(search.toLowerCase())
      )
    : data?.items ?? []

  return (
    <div>
      <PageHeader
        title="Gerenciamento de Usuários"
        description="Crie e gerencie contas de acesso ao sistema"
        action={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw className="w-3.5 h-3.5" />}
              onClick={() => refetch()}
            >
              Atualizar
            </Button>
            <Button
              icon={<Plus className="w-4 h-4" />}
              onClick={() => setCreateOpen(true)}
            >
              Novo Usuário
            </Button>
          </div>
        }
      />

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <Input
              placeholder="Buscar por nome ou email…"
              icon={<Search className="w-4 h-4" />}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="max-w-xs"
            />
            <div className="flex gap-1.5">
              {['', 'ADMIN', 'DOCTOR', 'ATTENDANT', 'PATIENT'].map((r) => (
                <button
                  key={r}
                  onClick={() => { setRoleFilter(r); setPage(1) }}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    roleFilter === r
                      ? 'bg-brand-500/15 text-brand-300'
                      : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/40'
                  }`}
                >
                  {r === '' ? 'Todos' : ROLE_LABELS[r]}
                </button>
              ))}
            </div>
          </div>
        </CardHeader>

        {isLoading ? (
          <PageLoader />
        ) : !filteredItems.length ? (
          <CardBody>
            <EmptyState
              icon={<Shield className="w-8 h-8" />}
              title="Nenhum usuário encontrado"
              action={
                <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>
                  Criar Usuário
                </Button>
              }
            />
          </CardBody>
        ) : (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>Usuário</Th>
                  <Th>Role</Th>
                  <Th>Status</Th>
                  <Th>Criado em</Th>
                  <Th>Ações</Th>
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    currentUserId={currentUser?.id ?? ''}
                    onDeactivate={setDeactivateTarget}
                    onEditRole={setEditRoleTarget}
                  />
                ))}
              </tbody>
            </Table>
            {data && (
              <Pagination
                page={page}
                total={data.total}
                size={20}
                onChange={setPage}
              />
            )}
          </>
        )}
      </Card>

      <CreateUserModal open={createOpen} onClose={() => setCreateOpen(false)} />
      <DeactivateModal
        user={deactivateTarget}
        open={!!deactivateTarget}
        onClose={() => setDeactivateTarget(null)}
      />
      <EditRoleModal
        user={editRoleTarget}
        open={!!editRoleTarget}
        onClose={() => setEditRoleTarget(null)}
      />
    </div>
  )
}
