# ETAPA 9 — FRONTEND SPA (REACT + TYPESCRIPT + TAILWINDCSS)

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Estrutura de Pastas](#3-estrutura-de-pastas)
4. [Roteamento e Guards](#4-roteamento-e-guards)
5. [Layout e Sidebar](#5-layout-e-sidebar)
6. [Páginas](#6-páginas)
7. [Componentes UI](#7-componentes-ui)
8. [Gerenciamento de Estado](#8-gerenciamento-de-estado)
9. [Camada de API](#9-camada-de-api)
10. [Hooks (TanStack Query)](#10-hooks-tanstack-query)
11. [Sistema de Tipos](#11-sistema-de-tipos)
12. [Utilitários](#12-utilitários)
13. [Design System](#13-design-system)
14. [Controle de Acesso por Role](#14-controle-de-acesso-por-role)
15. [Configuração e Deploy](#15-configuração-e-deploy)
16. [Variáveis de Ambiente](#16-variáveis-de-ambiente)

---

## 1. Visão Geral

O frontend do PROMPTUÁRIO é uma **Single Page Application (SPA)** construída em React 18 com TypeScript, que serve como interface gráfica para o sistema distribuído de prontuário eletrônico. Toda a comunicação com os microsserviços do backend é feita exclusivamente através do API Gateway em `http://localhost:8000/api/v1`.

### Características principais

- Autenticação JWT com refresh automático e fila de requisições concorrentes
- Roteamento protegido por role com `AuthGuard` e `RoleGuard`
- Carregamento lazy de páginas com Suspense
- Server state via TanStack Query (cache, invalidação, polling automático)
- Client state via Zustand com persist no `localStorage`
- Validação de formulários com Zod + React Hook Form
- Design system dark com paleta clínica teal customizada no Tailwind
- Polling automático para jobs assíncronos (IA e exportações)

### Fluxo de inicialização

```
main.tsx
  └── App.tsx
        ├── QueryClientProvider   (TanStack Query)
        ├── BrowserRouter         (React Router)
        ├── AppBootstrap          (carrega usuário do localStorage ao iniciar)
        └── AppRoutes             (árvore de rotas com lazy loading)
```

---

## 2. Stack Tecnológico

### Dependências de produção

| Pacote | Versão | Função |
|---|---|---|
| `react` + `react-dom` | ^18.3.1 | Framework base |
| `react-router-dom` | ^6.26.0 | Roteamento SPA |
| `@tanstack/react-query` | ^5.56.0 | Server state, cache, polling |
| `axios` | ^1.7.5 | HTTP client com interceptors |
| `zustand` | ^4.5.5 | Client state global |
| `react-hook-form` | ^7.53.0 | Gerenciamento de formulários |
| `zod` | ^3.23.8 | Validação de schemas |
| `@hookform/resolvers` | ^3.9.0 | Integração zod ↔ react-hook-form |
| `date-fns` | ^3.6.0 | Formatação de datas (locale pt-BR) |
| `lucide-react` | ^0.441.0 | Ícones |
| `recharts` | ^2.12.7 | Gráficos (dashboard e relatórios) |
| `clsx` + `tailwind-merge` | latest | Utilitário de classes CSS |

### Dependências de desenvolvimento

| Pacote | Função |
|---|---|
| `vite` ^5.4.2 | Build tool e dev server |
| `typescript` ^5.5.3 | Tipagem estática |
| `tailwindcss` ^3.4.10 | Utility-first CSS |
| `@vitejs/plugin-react` | HMR e JSX transform |
| `eslint` + plugins | Linting |

### Scripts disponíveis

```bash
npm run dev          # Servidor de desenvolvimento em :3000
npm run build        # Build de produção (tsc + vite build)
npm run preview      # Visualizar o build de produção
npm run lint         # ESLint em todos os arquivos ts/tsx
npm run type-check   # Verificação de tipos sem emitir arquivos
```

---

## 3. Estrutura de Pastas

```
promptuario-frontend/
│
├── index.html                    # Entry point HTML com meta tags
├── package.json
├── vite.config.ts                # Alias @/ → ./src, proxy /api → :8000
├── tailwind.config.ts            # Design system customizado
├── tsconfig.json                 # Strict mode, paths @/*
├── postcss.config.js
├── Dockerfile                    # Build multi-stage: Node → Nginx
├── nginx.conf                    # SPA fallback + proxy /api
├── .env.development              # VITE_API_BASE_URL=http://localhost:8000/api/v1
├── .env.production               # VITE_API_BASE_URL=https://api.promptuario.health/api/v1
│
└── src/
    ├── main.tsx                  # ReactDOM.createRoot
    ├── App.tsx                   # QueryClient, BrowserRouter, rotas
    ├── index.css                 # Tailwind directives, fontes, scrollbar
    │
    ├── api/
    │   ├── client.ts             # Axios instance, tokenStorage, interceptors JWT
    │   └── services.ts           # Todas as funções de chamada à API
    │
    ├── components/
    │   ├── layout/
    │   │   ├── AppShell.tsx      # Shell principal: Sidebar + TopBar + Outlet
    │   │   └── Sidebar.tsx       # Navegação lateral com filtro por role
    │   └── ui/
    │       └── index.tsx         # Biblioteca de componentes primitivos
    │
    ├── hooks/
    │   └── index.ts              # 25 hooks TanStack Query (queries + mutations)
    │
    ├── pages/
    │   ├── auth/
    │   │   └── LoginPage.tsx
    │   ├── dashboard/
    │   │   └── DashboardPage.tsx
    │   ├── patients/
    │   │   ├── PatientListPage.tsx
    │   │   └── PatientDetailPage.tsx
    │   ├── records/
    │   │   └── RecordsPage.tsx
    │   ├── appointments/
    │   │   └── AppointmentsPage.tsx
    │   ├── reports/
    │   │   └── ReportsPage.tsx
    │   └── admin/
    │       └── UserManagementPage.tsx
    │
    ├── store/
    │   └── auth.store.ts         # Zustand: auth state + actions
    │
    ├── types/
    │   └── index.ts              # Todas as interfaces TypeScript
    │
    └── utils/
        └── index.ts              # cn(), formatDate, ROLE_COLORS, etc.
```

---

## 4. Roteamento e Guards

### Árvore de rotas (`src/App.tsx`)

```
/login                              → LoginPage              [público]
/                                   → redirect → /dashboard

[AuthGuard]                         requer token JWT válido
  └── [AppShell]
        ├── /dashboard              → DashboardPage          [todos os roles]
        ├── /appointments           → AppointmentsPage       [todos os roles]
        │
        ├── [RoleGuard: ADMIN, DOCTOR, ATTENDANT]
        │     ├── /patients         → PatientListPage
        │     └── /patients/:id     → PatientDetailPage
        │
        ├── [RoleGuard: ADMIN, DOCTOR, PATIENT]
        │     ├── /records          → RecordsPage (lista)
        │     ├── /records/:recordId → RecordsPage (detalhe)
        │     └── /patients/:patientId/records → RecordsPage
        │
        ├── [RoleGuard: ADMIN, DOCTOR]
        │     └── /reports          → ReportsPage
        │
        └── [RoleGuard: ADMIN]
              └── /admin/users      → UserManagementPage

*                                   → página 404 inline
```

### `AuthGuard`

Verifica se o usuário está autenticado via `useAuthStore`. Se não, redireciona para `/login` preservando a rota de destino em `location.state.from`.

```typescript
// src/components/layout/AppShell.tsx
export function AuthGuard() {
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <Outlet />
}
```

### `RoleGuard`

Verifica se o `role` do usuário autenticado está na lista de roles permitidas. Em caso de falha, renderiza uma página 403 inline sem redirecionar.

```typescript
export function RoleGuard({ allowedRoles }: { allowedRoles: Role[] }) {
  const role = useAuthStore((s) => s.role)

  if (!hasRole(role, ...allowedRoles)) {
    return <div>403 — Acesso negado</div>
  }
  return <Outlet />
}
```

### Lazy loading

Todas as páginas são carregadas sob demanda com `React.lazy()` e `Suspense`. Enquanto carregam, o componente `PageLoader` é exibido (spinner centralizado).

```typescript
const DashboardPage = lazy(() =>
  import('@/pages/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage }))
)
```

### `QueryClient` — configuração global

```typescript
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,               // dados considerados frescos por 30s
      retry: (failureCount, error) => {
        if (error?.response?.status === 401) return false  // não retenta auth errors
        if (error?.response?.status === 403) return false
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
    },
    mutations: { retry: false },
  },
})
```

---

## 5. Layout e Sidebar

### `AppShell` (`src/components/layout/AppShell.tsx`)

Componente de layout principal que compõe `Sidebar` + `TopBar` + `<Outlet />` (conteúdo da página ativa).

```
┌─────────────────────────────────────────────────────────────┐
│  Sidebar (w-64, fixo)  │  TopBar (h-14, sticky)             │
│                        │──────────────────────────────────── │
│  Logo + navegação      │  Conteúdo da rota ativa (<Outlet>)  │
│  filtrada por role     │                                     │
│                        │                                     │
│  Avatar + logout       │                                     │
└─────────────────────────────────────────────────────────────┘
```

### `Sidebar` (`src/components/layout/Sidebar.tsx`)

A sidebar filtra os itens de navegação com base no `role` do usuário autenticado. Cada item define quais roles têm acesso:

```typescript
const NAV_ITEMS: NavItem[] = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: <LayoutDashboard />,
    roles: ['ADMIN', 'DOCTOR', 'ATTENDANT', 'PATIENT'],
  },
  {
    label: 'Pacientes',
    href: '/patients',
    icon: <UserRound />,
    roles: ['ADMIN', 'DOCTOR', 'ATTENDANT'],
  },
  {
    label: 'Consultas',
    href: '/appointments',
    icon: <Calendar />,
    roles: ['ADMIN', 'DOCTOR', 'ATTENDANT', 'PATIENT'],
  },
  {
    label: 'Prontuários',
    href: '/records',
    icon: <FileText />,
    roles: ['ADMIN', 'DOCTOR', 'PATIENT'],
  },
  {
    label: 'Análise IA',
    href: '/ai',
    icon: <Brain />,
    roles: ['ADMIN', 'DOCTOR'],
  },
  {
    label: 'Relatórios',
    href: '/reports',
    icon: <BarChart3 />,
    roles: ['ADMIN', 'DOCTOR'],
  },
  {
    label: 'Usuários',
    href: '/admin/users',
    icon: <Shield />,
    roles: ['ADMIN'],
  },
]
```

O link ativo é destacado visualmente com `NavLink` do React Router, que injeta a classe `isActive`. A seção inferior da sidebar exibe o avatar do usuário (iniciais) com nome, role e botão de logout.

### `PageHeader` (`src/components/layout/AppShell.tsx`)

Componente reutilizável para cabeçalho de página com suporte a título, descrição, breadcrumb e slot de ação (botão no canto direito).

```typescript
<PageHeader
  title="Pacientes"
  description="234 pacientes cadastrados"
  breadcrumb={[{ label: 'Dashboard' }, { label: 'Pacientes' }]}
  action={<Button icon={<Plus />}>Novo Paciente</Button>}
/>
```

---

## 6. Páginas

### `LoginPage` (`src/pages/auth/LoginPage.tsx`)

Página pública de autenticação com layout split: painel decorativo à esquerda e formulário à direita.

**Funcionalidades:**
- Formulário com `react-hook-form` + validação `zod`
- Toggle de visibilidade da senha
- Redirect automático se já autenticado (preserva rota de destino)
- Exibição de erros da API
- Credenciais de demo pré-preenchidas

**Schema de validação:**
```typescript
const schema = z.object({
  email: z.string().email('Email inválido'),
  password: z.string().min(6, 'Mínimo 6 caracteres'),
})
```

---

### `DashboardPage` (`src/pages/dashboard/DashboardPage.tsx`)

Dashboard adaptado ao role do usuário. Dois modos:

**Modo Admin/Doctor:**
- 4 `StatCard` com métricas do dia (consultas, novos pacientes, cancelamentos)
- `AreaChart` de consultas por dia da semana (Recharts)
- `BarChart` de consultas por especialidade
- Tabela de próximas consultas com link para `/appointments`

**Modo Patient:**
- Card de boas-vindas personalizado
- 3 quick actions (Minhas consultas, Meu prontuário, Histórico)
- Lista das últimas consultas com status

---

### `PatientListPage` (`src/pages/patients/PatientListPage.tsx`)

Lista paginada de pacientes com busca em tempo real (debounce 350ms).

**Funcionalidades:**
- Busca por nome com debounce
- Tabela com colunas: nome/email, CPF, idade calculada, tipo sanguíneo, telefone, status
- Clique na linha navega para o detalhe
- Modal de criação de paciente com seleção de usuário do sistema
- `EmptyState` com CTA quando lista está vazia

---

### `PatientDetailPage` (`src/pages/patients/PatientDetailPage.tsx`)

Visualização completa do paciente com sistema de abas.

**Abas disponíveis:**

| Aba | Conteúdo |
|---|---|
| Visão Geral | Endereço, contato, contato de emergência, observações |
| Alergias | Tabela com gravidade, tipo de reação; modal para adicionar |
| Vacinas | Cartão de vacinação com datas e próxima dose |
| Medicamentos | Medicamentos contínuos ativos com posologia |
| Consultas | Histórico de consultas do paciente |

O cabeçalho exibe badges de alergias e status ativo/inativo.

---

### `RecordsPage` (`src/pages/records/RecordsPage.tsx`)

Página dual: funciona como lista de prontuários de um paciente e como visualização de prontuário individual.

**Modo lista** (`/records` ou `/patients/:patientId/records`):
- Cards clicáveis com queixa principal, badges de prescrições e exames
- Botão de criação de prontuário (apenas DOCTOR)
- Modal de criação com formulário completo (queixa, anamnese, exame físico, diagnóstico, CID, plano terapêutico)

**Modo detalhe** (`/records/:recordId`):
- Seções: campos do prontuário, prescrições com medicamentos, solicitações de exame
- Botão "Análise IA" para solicitar análise de sintomas (DOCTOR only)
- Botão "Prescrição" abre modal com `useFieldArray` para múltiplos medicamentos
- Listagem de análises de IA com `risk_level` e recomendações

---

### `AppointmentsPage` (`src/pages/appointments/AppointmentsPage.tsx`)

Gestão de consultas com filtros de status e regras de negócio.

**Funcionalidades:**
- Filtros por status: Todas, Agendada, Confirmada, Concluída, Cancelada
- Modal de agendamento com seleção de paciente, médico, data/hora, tipo e especialidade
- Modal de cancelamento com validação de motivo (mínimo 5 chars)
- Regra de 24h aplicada no backend (retorna 422 se violada por PATIENT)
- Roles sem permissão de cancelamento: backend valida e retorna erro descritivo

---

### `ReportsPage` (`src/pages/reports/ReportsPage.tsx`)

Central de relatórios e exportações assíncronas.

**Funcionalidades:**
- 3 `StatCard` com resumo do dia (dados em tempo real via `useDashboardSummary`, refresh a cada 60s)
- `AreaChart` de consultas por dia (últimos 14 dias)
- Modal de exportação: tipo de relatório, formato (CSV/PDF/JSON), período
- Polling automático de jobs de exportação (a cada 5s, para quando `COMPLETED`)
- Download via redirect 302 para URL pre-assinada do MinIO S3

---

### `UserManagementPage` (`src/pages/admin/UserManagementPage.tsx`)

Gestão de usuários — exclusiva para ADMIN.

**Funcionalidades:**
- Tabela com avatar (iniciais), nome/email, role badge, status, data de criação
- Filtros por role e busca por nome/email (client-side)
- Modal de criação com validação de senha (maiúscula + número)
- Modal de alteração de role
- Modal de desativação com confirmação e motivo obrigatório
- Proteção para não desativar o próprio usuário (`isSelf`)

---

## 7. Componentes UI

Todos os componentes primitivos estão em `src/components/ui/index.tsx` e são exportados individualmente.

### `Button`

```typescript
<Button
  variant="primary" | "secondary" | "ghost" | "danger" | "outline"
  size="sm" | "md" | "lg"
  loading={boolean}
  icon={<ReactNode>}
  onClick={handler}
>
  Texto
</Button>
```

O estado `loading` substitui o ícone por um spinner `Loader2` e desabilita o botão.

### `Input` / `Textarea` / `Select`

Componentes controlados com `forwardRef` para integração com `react-hook-form`.

```typescript
<Input
  label="Email"
  type="email"
  placeholder="usuario@email.com"
  icon={<Mail className="w-4 h-4" />}
  suffix={<button>toggle</button>}
  error={errors.email?.message}
  hint="Texto de ajuda opcional"
  {...register('email')}
/>
```

### `Card` / `CardHeader` / `CardBody`

Contêiner com borda, backdrop-blur e sombra sutil. `Card` aceita `hover` para estilo clicável e `onClick` para navegação.

### `Modal`

Overlay com backdrop blur, animação `slide-up`, fechamento via botão X ou clique no fundo. Slot `footer` para botões de ação.

```typescript
<Modal
  open={isOpen}
  onClose={() => setOpen(false)}
  title="Título do Modal"
  size="sm" | "md" | "lg" | "xl"
  footer={<><Button variant="ghost">Cancelar</Button><Button>Salvar</Button></>}
>
  {/* conteúdo */}
</Modal>
```

### `Table` / `Th` / `Td`

Tabela semântica com overflow horizontal automático. `Th` aplica estilo de cabeçalho (uppercase, rastreamento de letras). `Td` inclui borda superior sutil entre linhas.

### `Badge`

Pill de status inline. Recebe `className` para colorir (use as constantes de `utils/index.ts`).

```typescript
<Badge className={STATUS_COLORS[appointment.status]}>
  {STATUS_LABELS[appointment.status]}
</Badge>
```

### `StatCard`

Card de métrica do dashboard com ícone colorido, valor grande, label e tendência opcional.

```typescript
<StatCard
  label="Consultas hoje"
  value={42}
  icon={<Calendar className="w-5 h-5" />}
  color="brand" | "violet" | "amber" | "rose"
  trend={{ value: '+12%', up: true }}
/>
```

### `Pagination`

Controle de paginação que só renderiza se `totalPages > 1`. Exibe range de registros visíveis.

### `EmptyState`

Estado vazio com ícone, título, descrição e slot de ação.

### `Alert`

Alerta inline com variantes: `error`, `warning`, `info`, `success`.

### `PageLoader` / `Spinner`

`PageLoader` — spinner centralizado em `min-h-[400px]`, usado como fallback de `Suspense`.  
`Spinner` — ícone `Loader2` com `animate-spin`, tamanhos `sm/md/lg`.

---

## 8. Gerenciamento de Estado

### Auth Store (`src/store/auth.store.ts`)

Store global de autenticação construída com Zustand + middleware `persist`. Os dados são persistidos em `localStorage` com a chave `promptuario-auth`.

**Interface do estado:**

```typescript
interface AuthState {
  user: User | null
  role: Role | null
  isAuthenticated: boolean
  isLoading: boolean

  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  loadUser: () => Promise<void>
  setUser: (user: User) => void
}
```

**Fluxo de `login`:**

1. Chama `authApi.login()` → recebe `{ access_token, refresh_token }`
2. Persiste tokens em `localStorage` via `tokenStorage.set()`
3. Decodifica o JWT localmente para extrair `role`
4. Chama `authApi.me()` para buscar dados completos do usuário
5. Atualiza o estado: `{ user, role, isAuthenticated: true }`

**Fluxo de `loadUser` (bootstrap):**

Executado uma vez ao montar o `AppBootstrap`. Verifica se há token no `localStorage`, decodifica e valida a expiração. Se válido, chama `/users/me` para restaurar o estado. Se inválido, limpa o storage.

**Seletores exportados:**

```typescript
export const useRole = () => useAuthStore((s) => s.role)
export const useUser = () => useAuthStore((s) => s.user)
export const useIsAdmin = () => useAuthStore((s) => s.role === 'ADMIN')
export const useIsDoctor = () => useAuthStore((s) => s.role === 'DOCTOR')
export const useIsAttendant = () => useAuthStore((s) => s.role === 'ATTENDANT')
export const useIsPatient = () => useAuthStore((s) => s.role === 'PATIENT')

// Verificação de múltiplos roles
export const hasRole = (role: Role | null, ...allowedRoles: Role[]): boolean =>
  role !== null && allowedRoles.includes(role)
```

---

## 9. Camada de API

### `src/api/client.ts` — Axios com interceptors JWT

**`tokenStorage`** — abstração para acesso ao `localStorage`:

```typescript
export const tokenStorage = {
  getAccess: () => localStorage.getItem('access_token'),
  getRefresh: () => localStorage.getItem('refresh_token'),
  set: (tokens: AuthTokens) => { /* persiste ambos */ },
  clear: () => { /* remove ambos */ },
}
```

**Request interceptor** — injeta `Authorization: Bearer <token>` em todas as requisições autenticadas.

**Response interceptor — auto-refresh em 401:**

O interceptor implementa uma fila de requisições para lidar com múltiplas chamadas simultâneas que recebem 401:

1. Primeira requisição com 401 inicia o refresh
2. Outras requisições com 401 são enfileiradas (`refreshQueue`)
3. Após refresh bem-sucedido: todos na fila recebem o novo token e são reenviados
4. Se o refresh falha: fila é rejeitada, tokens limpos, redirect para `/login`

```typescript
let isRefreshing = false
let refreshQueue: Array<{
  resolve: (token: string) => void
  reject: (err: unknown) => void
}> = []
```

Este padrão evita múltiplos requests de refresh simultâneos e garante que nenhuma requisição seja perdida durante a renovação do token.

### `src/api/services.ts` — Funções de API por domínio

Organizado em objetos por serviço, cada função retorna diretamente o dado tipado (`.then(r => r.data)`):

```typescript
export const authApi = {
  login, logout, refresh, changePassword, me
}

export const usersApi = {
  list, get, create, update, assignRole, deactivate
}

export const patientsApi = {
  list, get, summary, create, update, deactivate,
  listAllergies, addAllergy, deleteAllergy,
  listVaccines, addVaccine,
  listMedications, addMedication, deleteMedication,
}

export const appointmentsApi = {
  list, get, create, cancel, complete
}

export const recordsApi = {
  listByPatient, get, create, update,
  createPrescription, downloadPrescription,
  createExam, recordResult,
}

export const aiApi = {
  analyze, getJob, listByRecord
}

export const reportsApi = {
  summary, consultations, patients, doctors,
  requestExport, getExportJob, downloadExport,
}
```

---

## 10. Hooks (TanStack Query)

Todos os hooks estão em `src/hooks/index.ts`. Seguem o padrão de **query keys tipadas** para invalidação precisa do cache.

### Query Keys

```typescript
export const keys = {
  users: {
    all: ['users'],
    list: (params?) => ['users', 'list', params],
    detail: (id) => ['users', id],
  },
  patients: {
    all: ['patients'],
    list: (params?) => ['patients', 'list', params],
    detail: (id) => ['patients', id],
    summary: (id) => ['patients', id, 'summary'],
    allergies: (id) => ['patients', id, 'allergies'],
    vaccines: (id) => ['patients', id, 'vaccines'],
    medications: (id) => ['patients', id, 'medications'],
  },
  appointments: {
    all: ['appointments'],
    list: (params?) => ['appointments', 'list', params],
    detail: (id) => ['appointments', id],
  },
  records: {
    all: ['records'],
    byPatient: (patientId) => ['records', 'patient', patientId],
    detail: (id) => ['records', id],
  },
  ai: {
    job: (jobId) => ['ai', 'job', jobId],
    byRecord: (recordId) => ['ai', 'record', recordId],
  },
  reports: {
    summary: ['reports', 'summary'],
    consultations: (params?) => ['reports', 'consultations', params],
    job: (jobId) => ['reports', 'job', jobId],
  },
}
```

### Hooks de queries

| Hook | Query key | Habilitado |
|---|---|---|
| `useUsers(params?)` | `keys.users.list(params)` | sempre |
| `useUser(id)` | `keys.users.detail(id)` | `!!id` |
| `usePatients(params?)` | `keys.patients.list(params)` | sempre |
| `usePatient(id)` | `keys.patients.detail(id)` | `!!id` |
| `usePatientSummary(id)` | `keys.patients.summary(id)` | `!!id` |
| `usePatientAllergies(id)` | `keys.patients.allergies(id)` | `!!id` |
| `usePatientVaccines(id)` | `keys.patients.vaccines(id)` | `!!id` |
| `usePatientMedications(id)` | `keys.patients.medications(id)` | `!!id` |
| `useAppointments(params?)` | `keys.appointments.list(params)` | sempre |
| `useAppointment(id)` | `keys.appointments.detail(id)` | `!!id` |
| `usePatientRecords(patientId)` | `keys.records.byPatient(id)` | `!!patientId` |
| `useRecord(id)` | `keys.records.detail(id)` | `!!id` |
| `useRecordAnalyses(recordId)` | `keys.ai.byRecord(id)` | `!!recordId` |
| `useDashboardSummary()` | `keys.reports.summary` | sempre, `refetchInterval: 60_000` |
| `useConsultationsReport(params?)` | `keys.reports.consultations(params)` | sempre |

### Hooks de mutations

| Hook | Invalidação automática |
|---|---|
| `useCreateUser()` | `keys.users.all` |
| `useDeactivateUser()` | `keys.users.all` |
| `useCreatePatient()` | `keys.patients.all` |
| `useUpdatePatient()` | `keys.patients.detail(id)` + `summary(id)` |
| `useAddAllergy()` | `keys.patients.allergies(patientId)` |
| `useDeleteAllergy()` | `keys.patients.allergies(patientId)` |
| `useCreateAppointment()` | `keys.appointments.all` |
| `useCancelAppointment()` | `keys.appointments.all` |
| `useCreateRecord()` | `keys.records.byPatient(patient_id)` |
| `useCreatePrescription()` | `keys.records.detail(recordId)` |

### Hooks com polling automático

`useAnalysisJob(jobId)` e `useExportJob(jobId)` usam `refetchInterval` condicional — fazem polling a cada 3s e 5s respectivamente enquanto o status for `PENDING` ou `RUNNING`, e param automaticamente quando `COMPLETED` ou `FAILED`:

```typescript
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
```

---

## 11. Sistema de Tipos

Todas as interfaces TypeScript estão em `src/types/index.ts` e refletem os schemas Pydantic do backend.

### Tipos de autenticação

```typescript
type Role = 'ADMIN' | 'DOCTOR' | 'ATTENDANT' | 'PATIENT'

interface TokenPayload {
  sub: string       // user_id
  role: Role
  email: string
  exp: number
  iat: number
  type: 'access' | 'refresh'
}

interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}
```

### Tipos de domínio principais

```typescript
interface User {
  id: string; email: string; full_name: string
  role: Role; is_active: boolean
  created_at: string; updated_at: string
}

interface Patient {
  id: string; user_id: string; full_name: string
  cpf: string | null; date_of_birth: string | null
  gender: 'M' | 'F' | 'OTHER' | null; blood_type: string | null
  phone: string | null; email: string | null
  // endereço: street, city, state, zip_code
  // emergência: emergency_name, emergency_phone, emergency_relation
  is_active: boolean; created_at: string; updated_at: string
}

interface PatientSummary extends Patient {
  allergies: Allergy[]
  medications: ContinuousMedication[]
}

interface Appointment {
  id: string; patient_id: string; doctor_id: string
  scheduled_at: string
  appointment_type: 'CONSULTATION' | 'RETURN' | 'EXAM' | 'URGENT'
  specialty: string | null
  status: 'SCHEDULED' | 'CONFIRMED' | 'COMPLETED' | 'CANCELLED' | 'NO_SHOW'
  cancellation_reason: string | null
  notes: string | null; created_at: string
}

interface MedicalRecord {
  id: string; appointment_id: string
  patient_id: string; doctor_id: string
  chief_complaint: string; anamnesis: string | null
  physical_exam: string | null; diagnosis: string | null
  diagnosis_codes: string[]
  treatment_plan: string | null; observations: string | null
  ai_analysis_id: string | null
  prescriptions: Prescription[]
  exam_requests: ExamRequest[]
  created_at: string; updated_at: string
}

interface AnalysisJob {
  id: string
  analysis_type: 'DRUG_INTERACTION_CHECK' | 'SYMPTOM_ANALYSIS' | 'CLINICAL_SUMMARY'
  patient_id: string; record_id: string | null
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  risk_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | null
  result: Record<string, unknown> | null
  model_version: string
  created_at: string; completed_at: string | null
}

interface PaginatedResponse<T> {
  items: T[]; total: number; page: number; size: number
}
```

---

## 12. Utilitários

Arquivo: `src/utils/index.ts`

### `cn(...inputs)`

Merge de classes Tailwind com suporte a condicionais via `clsx` + `tailwind-merge`. Elimina conflitos de classes duplicadas.

```typescript
cn('px-4 py-2', isActive && 'bg-brand-500', 'px-4')
// → 'py-2 bg-brand-500 px-4'  (px-4 duplicado resolvido)
```

### Formatadores de data

```typescript
formatDate(date, pattern?)     // 'dd/MM/yyyy' por padrão, locale pt-BR
formatDateTime(date)           // "dd/MM/yyyy 'às' HH:mm"
formatRelative(date)           // "há 3 horas", "em 2 dias" (date-fns)
calculateAge(dateOfBirth)      // número inteiro de anos ou null
```

### Formatadores de texto

```typescript
formatCPF(cpf)    // '12345678900' → '123.456.789-00'
initials(name)    // 'João da Silva' → 'JS'
truncate(str, maxLen)
```

### Constantes de visualização

```typescript
// Labels em português
ROLE_LABELS: { ADMIN: 'Administrador', DOCTOR: 'Médico', ... }

// Classes Tailwind para Badge por role
ROLE_COLORS: {
  ADMIN:     'bg-violet-500/15 text-violet-300 ring-violet-500/20',
  DOCTOR:    'bg-brand-500/15 text-brand-300 ring-brand-500/20',
  ATTENDANT: 'bg-sky-500/15 text-sky-300 ring-sky-500/20',
  PATIENT:   'bg-slate-500/15 text-slate-400 ring-slate-500/20',
}

// Labels e cores de status de consulta
STATUS_LABELS: { SCHEDULED: 'Agendada', CONFIRMED: 'Confirmada', ... }
STATUS_COLORS: { SCHEDULED: 'bg-sky-500/15 text-sky-300', ... }

// Cores de gravidade de alergia
SEVERITY_COLORS: { MILD: 'bg-amber-500/15 text-amber-300', ... }

// Cores de nível de risco de IA
RISK_COLORS: { LOW: 'text-emerald-400', MEDIUM: 'text-amber-400', ... }
```

### Utilitários de arquivo

```typescript
// Download de Blob (CSV, PDF)
downloadBlob(blob: Blob, filename: string): void

// Extração de mensagem de erro do Axios
getErrorMessage(error: unknown): string
// Retorna error.response.data.detail ou 'Erro desconhecido'
```

---

## 13. Design System

### Paleta de cores (`tailwind.config.ts`)

O design system usa uma paleta dark com destaque clínico teal (`brand`):

```
bg-slate-950   (#090d14)  — fundo da aplicação
bg-slate-900   (#0f172a)  — superfície de cards
bg-slate-800   (#1e293b)  — bordas e hovers
brand-500      (#1ab0a4)  — cor primária de ação
brand-400      (#38ccbe)  — hover de elementos brand
brand-300      (#71e4d5)  — texto brand em fundos escuros
```

### Tipografia

- **Body/UI:** `DM Sans` — legibilidade em interfaces dense
- **Headings/Títulos:** `Sora` (600/700) — `font-display`
- **Código/Monospace:** `JetBrains Mono` — `font-mono`

### Sombras customizadas

```css
shadow-card       /* superfície de card base */
shadow-card-hover /* card em hover com borda brand */
shadow-modal      /* overlay de modal */
shadow-glow-brand /* brilho teal para elementos ativos */
shadow-glow-sm    /* brilho sutil */
```

### Animações

```css
animate-fade-in       /* opacity 0→1, 200ms */
animate-slide-up      /* opacity+translateY, 250ms */
animate-slide-in-right
animate-pulse-brand   /* pulsação teal para status pendente */
```

### Grid de fundo

Disponível via `bg-grid-pattern bg-grid` — grid sutil de 24×24px para painéis decorativos.

---

## 14. Controle de Acesso por Role

### Matriz de permissões por funcionalidade

| Funcionalidade | PATIENT | ATTENDANT | DOCTOR | ADMIN |
|---|:---:|:---:|:---:|:---:|
| Acessar dashboard | ✅ | ✅ | ✅ | ✅ |
| Ver próprias consultas | ✅ | — | — | ✅ |
| Ver todas as consultas | — | ✅ | ✅ | ✅ |
| Agendar consulta | ✅ | ✅ | — | ✅ |
| Cancelar consulta | ✅* | ✅ | ✅ | ✅ |
| Listar pacientes | — | ✅ | ✅ | ✅ |
| Criar paciente | — | ✅ | — | ✅ |
| Ver próprio prontuário | ✅ | — | — | ✅ |
| Ver qualquer prontuário | — | — | ✅ | ✅ |
| Criar prontuário | — | — | ✅ | — |
| Gerar prescrição | — | — | ✅ | — |
| Solicitar análise IA | — | — | ✅ | ✅ |
| Acessar relatórios | — | — | ✅ | ✅ |
| Exportar relatórios | — | — | ✅ | ✅ |
| Gerenciar usuários | — | — | — | ✅ |

`*` Regra de 24h aplicada pelo backend: PATIENT recebe 422 se cancelar com menos de 24h de antecedência.

### Implementação em camadas

A proteção ocorre em três camadas independentes:

**Camada 1 — Roteamento** (`RoleGuard` em `App.tsx`): impede acesso à página.

**Camada 2 — UI** (botões condicionais nas páginas): oculta ações não permitidas.

**Camada 3 — API Gateway** (backend): rejeita requisições com role incorreto retornando `403 Forbidden`.

---

## 15. Configuração e Deploy

### Desenvolvimento local

```bash
# 1. Instalar dependências
npm install

# 2. Backend deve estar rodando
# (docker compose up a partir do promptuario-backend)

# 3. Iniciar frontend
npm run dev
# → http://localhost:3000
```

O `vite.config.ts` configura proxy para `/api` → `http://localhost:8000`, então não há problemas de CORS em desenvolvimento.

### Build de produção

```bash
npm run build
# Gera dist/ com assets hasheados
```

### Docker — build multi-stage

```dockerfile
# Stage 1: Node 20 compila o React
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --frozen-lockfile
COPY . .
RUN npm run build

# Stage 2: Nginx 1.27 serve os assets
FROM nginx:1.27-alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### Nginx — SPA fallback

O `nginx.conf` configura:
- SPA fallback: todas as rotas não encontradas servem `index.html`
- Cache agressivo de assets estáticos (`js`, `css`, imagens): 1 ano
- Cache `no-store` para `index.html`
- Proxy `/api/` → `http://gateway:8000`
- Gzip habilitado para `js`, `css`, `json`, `svg`

---

## 16. Variáveis de Ambiente

| Variável | Desenvolvimento | Produção | Descrição |
|---|---|---|---|
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | `https://api.promptuario.health/api/v1` | Base URL do API Gateway |

As variáveis `VITE_*` são injetadas pelo Vite no build e ficam disponíveis em `import.meta.env.VITE_*`.

> **Atenção:** nunca coloque segredos (API keys, tokens) em variáveis `VITE_*`. Elas ficam expostas no bundle JS do cliente.

---

## Apêndice — Fluxo JWT completo

```
1. Usuário faz login
   POST /auth/login → { access_token (30min), refresh_token (7d) }
   tokenStorage.set() → localStorage

2. Requisições autenticadas
   Request interceptor → Authorization: Bearer <access_token>

3. Token expira (401 recebido)
   Response interceptor detecta 401
   └── Se isRefreshing=false: inicia refresh
       POST /auth/refresh → novos tokens
       tokenStorage.set() → atualiza localStorage
       Reprocessa requisição original
   └── Se isRefreshing=true: enfileira na refreshQueue
       Aguarda tokens novos, reprocessa com novo token

4. Refresh falha (token revogado/expirado)
   tokenStorage.clear()
   window.location.href = '/login'

5. Logout
   POST /auth/logout → revoga refresh_token no backend
   tokenStorage.clear()
   useAuthStore.setState({ user: null, isAuthenticated: false })
   navigate('/login')
```

---