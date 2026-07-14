import { useState, useEffect } from 'react'
import { Shield, Search, Filter, AlertTriangle, Activity, Clock, UserCircle, Database, FileText } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { auditApi } from '@/api/services'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Input, Select, Modal,
  Table, Th, Td, Badge, PageLoader, EmptyState, Pagination,
  Alert, Spinner,
} from '@/components/ui'
import { formatDateTime, getErrorMessage, cn } from '@/utils'

const OPERATION_LABELS: Record<string, string> = {
  INSERT: 'Inserção',
  UPDATE: 'Atualização',
  DELETE: 'Exclusão',
  AUTH_LOGIN: 'Login',
  AUTH_LOGOUT: 'Logout',
  PASSWORD_CHANGE: 'Troca de Senha',
}

const OPERATION_COLORS: Record<string, string> = {
  INSERT: 'bg-emerald-500/15 text-emerald-300 ring-emerald-600/30',
  UPDATE: 'bg-amber-500/15 text-amber-300 ring-amber-600/30',
  DELETE: 'bg-rose-500/15 text-rose-300 ring-rose-600/30',
  AUTH_LOGIN: 'bg-sky-500/15 text-sky-300 ring-sky-600/30',
  AUTH_LOGOUT: 'bg-slate-500/15 text-slate-300 ring-slate-600/30',
  PASSWORD_CHANGE: 'bg-purple-500/15 text-purple-300 ring-purple-600/30',
}

const SERVICE_LABELS: Record<string, string> = {
  'iam-service': 'IAM',
  'patient-service': 'Pacientes',
  'clinical-service': 'Clínico',
}

const SEVERITY_COLORS: Record<string, string> = {
  LOW: 'bg-slate-500/15 text-slate-300',
  MEDIUM: 'bg-amber-500/15 text-amber-300',
  HIGH: 'bg-orange-500/15 text-orange-300',
  CRITICAL: 'bg-rose-500/15 text-rose-300',
}

// ─── Summary Tab ────────────────────────────────────────────────────────────
function SummaryTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['audit', 'summary'],
    queryFn: () => auditApi.summary(),
    refetchInterval: 60_000,
  })

  if (isLoading) return <PageLoader />

  if (!data) return <Alert variant="error">Erro ao carregar resumo.</Alert>

  const maxOp = Math.max(...Object.values(data.by_operation), 1)
  const maxSvc = Math.max(...Object.values(data.by_service), 1)
  const maxTbl = Math.max(...Object.values(data.by_table), 1)

  return (
    <div className="space-y-6">
      {/* Total */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardBody>
            <div className="text-center">
              <div className="text-3xl font-bold text-slate-100">{data.total}</div>
              <div className="text-xs text-slate-500 mt-1">Total de Eventos (30d)</div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <div className="text-center">
              <div className="text-3xl font-bold text-emerald-400">
                {Object.keys(data.by_service).length}
              </div>
              <div className="text-xs text-slate-500 mt-1">Serviços Auditados</div>
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <div className="text-center">
              <div className="text-3xl font-bold text-sky-400">
                {Object.keys(data.by_table).length}
              </div>
              <div className="text-xs text-slate-500 mt-1">Tabelas Monitoradas</div>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Por Operação */}
      <Card>
        <CardHeader><span className="text-sm font-semibold text-slate-200">Eventos por Operação</span></CardHeader>
        <CardBody>
          <div className="space-y-3">
            {Object.entries(data.by_operation)
              .sort(([, a], [, b]) => b - a)
              .map(([op, count]) => (
                <div key={op} className="flex items-center gap-4">
                  <Badge className={cn('w-24 text-center', OPERATION_COLORS[op] || 'bg-slate-700/40')}>
                    {OPERATION_LABELS[op] || op}
                  </Badge>
                  <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-brand-500/60 rounded-full transition-all"
                      style={{ width: `${(count / maxOp) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-slate-400 w-12 text-right">{count}</span>
                </div>
              ))}
          </div>
        </CardBody>
      </Card>

      {/* Por Serviço */}
      <Card>
        <CardHeader><span className="text-sm font-semibold text-slate-200">Eventos por Serviço</span></CardHeader>
        <CardBody>
          <div className="space-y-3">
            {Object.entries(data.by_service)
              .sort(([, a], [, b]) => b - a)
              .map(([svc, count]) => (
                <div key={svc} className="flex items-center gap-4">
                  <Badge className="w-24 text-center bg-slate-700/40 text-slate-300">
                    {SERVICE_LABELS[svc] || svc}
                  </Badge>
                  <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-sky-500/60 rounded-full transition-all"
                      style={{ width: `${(count / maxSvc) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-slate-400 w-12 text-right">{count}</span>
                </div>
              ))}
          </div>
        </CardBody>
      </Card>

      {/* Por Tabela */}
      <Card>
        <CardHeader><span className="text-sm font-semibold text-slate-200">Eventos por Tabela</span></CardHeader>
        <CardBody>
          <div className="space-y-3">
            {Object.entries(data.by_table)
              .sort(([, a], [, b]) => b - a)
              .map(([tbl, count]) => (
                <div key={tbl} className="flex items-center gap-4">
                  <Badge className="w-32 text-center bg-slate-700/40 text-slate-300">
                    {tbl}
                  </Badge>
                  <div className="flex-1 h-3 bg-slate-800 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500/60 rounded-full transition-all"
                      style={{ width: `${(count / maxTbl) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-slate-400 w-12 text-right">{count}</span>
                </div>
              ))}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}

// ─── Suspicious Tab ─────────────────────────────────────────────────────────
function SuspiciousTab() {
  const { data, isLoading } = useQuery({
    queryKey: ['audit', 'suspicious'],
    queryFn: () => auditApi.suspicious(),
    refetchInterval: 30_000,
  })

  if (isLoading) return <PageLoader />

  if (!data) return <Alert variant="error">Erro ao carregar atividades suspeitas.</Alert>

  const iconMap: Record<string, React.ReactNode> = {
    BRUTE_FORCE_ATTEMPT: <Shield className="w-5 h-5 text-rose-400" />,
    EXCESSIVE_DELETES: <AlertTriangle className="w-5 h-5 text-orange-400" />,
  }

  return (
    <div className="space-y-4">
      {data.alerts.length === 0 ? (
        <EmptyState
          icon={<Shield className="w-8 h-8 text-emerald-400" />}
          title="Nenhuma atividade suspeita nos últimos 7 dias"
          description="Todas as operações estão dentro dos limites de segurança."
        />
      ) : (
        <>
          <div className="flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
            <span className="text-sm text-slate-300">
              <strong className="text-rose-400">{data.total_alerts}</strong> alerta(s) nos últimos 7 dias
            </span>
          </div>
          <div className="space-y-3">
            {data.alerts.map((alert, i) => (
              <Card key={i}>
                <CardBody>
                  <div className="flex items-start gap-4">
                    <div className="mt-0.5">{iconMap[alert.type] || <AlertTriangle className="w-5 h-5 text-slate-400" />}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <Badge className={SEVERITY_COLORS[alert.severity]}>
                          {alert.severity}
                        </Badge>
                        <span className="text-sm font-medium text-slate-200">
                          {alert.type === 'BRUTE_FORCE_ATTEMPT' ? 'Tentativa de Força Bruta' : 'Exclusões em Massa'}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500 space-y-0.5">
                        <p>Serviço: <span className="text-slate-400">{SERVICE_LABELS[alert.service] || alert.service}</span></p>
                        {alert.user_email && <p>Email: <span className="text-slate-400">{alert.user_email}</span></p>}
                        <p>Total: <span className="text-slate-400">{alert.count} ocorrência(s)</span></p>
                        {alert.period_hour && <p>Horário: <span className="text-slate-400">{alert.period_hour}</span></p>}
                      </div>
                    </div>
                  </div>
                </CardBody>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

// ─── Logs Tab ───────────────────────────────────────────────────────────────
function LogsTab() {
  const [page, setPage] = useState(1)
  const [serviceFilter, setServiceFilter] = useState('')
  const [operationFilter, setOperationFilter] = useState('')
  const [tableFilter, setTableFilter] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['audit', 'logs', { page, service: serviceFilter, operation: operationFilter, table: tableFilter }],
    queryFn: () => auditApi.logs({
      page,
      size: 50,
      service: serviceFilter || undefined,
      operation: operationFilter || undefined,
      table_name: tableFilter || undefined,
    }),
  })

  const handleExport = async () => {
    try {
      await auditApi.exportLogs({
        service: serviceFilter || undefined,
        operation: operationFilter || undefined,
        table_name: tableFilter || undefined,
      })
    } catch (err) {
      console.error('Failed to export', err)
    }
  }

  return (
    <div>
      <div className="flex flex-wrap items-end gap-3 mb-4">
        <Select
          label="Serviço"
          options={[
            { value: '', label: 'Todos' },
            { value: 'iam-service', label: 'IAM' },
            { value: 'patient-service', label: 'Pacientes' },
            { value: 'clinical-service', label: 'Clínico' },
          ]}
          value={serviceFilter}
          onChange={(e) => { setServiceFilter(e.target.value); setPage(1) }}
          className="w-40"
        />
        <Select
          label="Operação"
          options={[
            { value: '', label: 'Todas' },
            ...Object.entries(OPERATION_LABELS).map(([v, l]) => ({ value: v, label: l })),
          ]}
          value={operationFilter}
          onChange={(e) => { setOperationFilter(e.target.value); setPage(1) }}
          className="w-40"
        />
        <Input
          label="Tabela"
          placeholder="Filtrar por tabela…"
          value={tableFilter}
          onChange={(e) => { setTableFilter(e.target.value); setPage(1) }}
          className="w-48"
        />
        <div className="flex-1" />
        <Button variant="outline" icon={<FileText className="w-4 h-4" />} onClick={handleExport}>
          Exportar (CSV)
        </Button>
      </div>

      {isLoading ? (
        <PageLoader />
      ) : !data?.items.length ? (
        <EmptyState
          icon={<Search className="w-8 h-8" />}
          title="Nenhum log encontrado"
          description="Tente alterar os filtros ou aguarde mais operações no sistema."
        />
      ) : (
        <>
          <div className="overflow-x-auto">
            <Table>
              <thead>
                <tr>
                  <Th>Data/Hora</Th>
                  <Th>Serviço</Th>
                  <Th>Operação</Th>
                  <Th>Tabela</Th>
                  <Th>Registro</Th>
                  <Th>Usuário</Th>
                  <Th>IP / Máquina</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((log: any, i: number) => (
                  <tr key={i} className="hover:bg-slate-800/20 transition-colors">
                    <Td>
                      <div className="flex items-center gap-2">
                        <Clock className="w-3.5 h-3.5 text-slate-600" />
                        <span className="text-xs text-slate-300">
                          {formatDateTime(log.timestamp)}
                        </span>
                      </div>
                    </Td>
                    <Td>
                      <Badge className="bg-slate-700/40 text-slate-300">
                        {SERVICE_LABELS[log.service_name] || log.service_name}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge className={OPERATION_COLORS[log.operation] || 'bg-slate-700/40'}>
                        {OPERATION_LABELS[log.operation] || log.operation}
                      </Badge>
                    </Td>
                    <Td>
                      <Badge className="bg-slate-700/40 text-slate-300">
                        {log.table_name}
                      </Badge>
                    </Td>
                    <Td>
                      <span className="text-xs text-slate-400 font-mono">
                        {log.record_id ? log.record_id.substring(0, 8) + '…' : '—'}
                      </span>
                    </Td>
                    <Td>
                      <span className="text-xs text-slate-400">
                        {log.user_email || log.user_id?.substring(0, 8) || '—'}
                      </span>
                    </Td>
                    <Td>
                      <span className="text-xs text-slate-400 font-mono">
                        {log.ip_address || '—'}
                      </span>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
          <Pagination page={page} total={data.total} size={50} onChange={setPage} />
        </>
      )}
    </div>
  )
}

// ─── Page ───────────────────────────────────────────────────────────────────
const TABS = [
  { key: 'summary', label: '📊 Resumo' },
  { key: 'suspicious', label: '🚨 Atividades Suspeitas' },
  { key: 'logs', label: '📋 Logs Detalhados' },
] as const

export function AuditPage() {
  const [activeTab, setActiveTab] = useState<'summary' | 'suspicious' | 'logs'>('summary')

  return (
    <div>
      <PageHeader
        title="Auditoria"
        description="Monitoramento de operações críticas no sistema"
      />

      {/* Tab buttons */}
      <div className="flex gap-1 mb-6 p-1 bg-slate-900/80 border border-slate-800/60 rounded-xl w-fit">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-4 py-2 rounded-lg text-sm font-medium transition-all duration-150',
              activeTab === tab.key
                ? 'bg-brand-500/15 text-brand-300 shadow-sm'
                : 'text-slate-500 hover:text-slate-300'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'summary' && <SummaryTab />}
      {activeTab === 'suspicious' && <SuspiciousTab />}
      {activeTab === 'logs' && <LogsTab />}
    </div>
  )
}
