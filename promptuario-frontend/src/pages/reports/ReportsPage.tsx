import { useState } from 'react'
import {
  BarChart3, Download, RefreshCw, Calendar,
  FileText, Users, Stethoscope, Clock, CheckCircle,
  AlertCircle, Loader2,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, BarChart, Bar,
} from 'recharts'
import {
  useConsultationsReport, useRequestExport, useExportJob,
  useDashboardSummary,
} from '@/hooks'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Select, Modal,
  Badge, PageLoader, StatCard, Alert, Spinner,
} from '@/components/ui'
import { formatDate, formatDateTime, getErrorMessage, cn } from '@/utils'
import { reportsApi } from '@/api/services'
import type { ReportType, OutputFormat, ReportJob } from '@/types'

const CHART_COLORS = { brand: '#1ab0a4', violet: '#8b5cf6', amber: '#f59e0b' }

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs shadow-modal">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} className="font-semibold text-slate-200">{p.value} {p.name}</p>
      ))}
    </div>
  )
}

// ─── Export Job Status Widget ─────────────────────────────────────────────
function ExportJobStatus({ jobId }: { jobId: string }) {
  const { data: job } = useExportJob(jobId)

  if (!job) return <Spinner size="sm" />

  const handleDownload = async () => {
    try {
      const response = await reportsApi.downloadExport(jobId)
      
      // If the response contains a JSON with 'url'
      if (response.data && response.data.url) {
        window.open(response.data.url, '_self')
      } else {
        // Fallback for Blob (if backend still returns raw file)
        const blob = new Blob([response.data])
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `relatorio_${job.report_type.toLowerCase()}_${jobId.slice(0, 8)}.${job.output_format.toLowerCase()}`
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (err) {
      alert("Erro ao realizar o download do arquivo.")
    }
  }

  return (
    <div className={cn(
      'flex items-center justify-between p-4 rounded-xl border',
      job.status === 'COMPLETED' ? 'bg-emerald-500/5 border-emerald-500/20' :
      job.status === 'FAILED' ? 'bg-rose-500/5 border-rose-500/20' :
      'bg-slate-900/60 border-slate-800/60',
    )}>
      <div className="flex items-center gap-3">
        {job.status === 'COMPLETED' ? (
          <CheckCircle className="w-4 h-4 text-emerald-400" />
        ) : job.status === 'FAILED' ? (
          <AlertCircle className="w-4 h-4 text-rose-400" />
        ) : (
          <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
        )}
        <div>
          <p className="text-sm font-medium text-slate-200">
            {job.report_type === 'FULL_SYSTEM' ? 'RELATÓRIO COMPLETO' : job.report_type} · {job.output_format}
          </p>
          <p className="text-xs text-slate-500">
            {job.status === 'COMPLETED'
              ? `${job.row_count} registros · ${formatDateTime(job.completed_at)}`
              : job.status === 'FAILED'
              ? job.error_message
              : 'Gerando relatório…'}
          </p>
        </div>
      </div>
      {job.status === 'COMPLETED' && (
        <Button
          size="sm"
          variant="secondary"
          icon={<Download className="w-3.5 h-3.5" />}
          onClick={handleDownload}
        >
          Baixar
        </Button>
      )}
    </div>
  )
}

// ─── Export Modal ─────────────────────────────────────────────────────────
function ExportModal({
  open,
  onClose,
  onJobCreated,
}: {
  open: boolean
  onClose: () => void
  onJobCreated: (jobId: string) => void
}) {
  const [reportType, setReportType] = useState<ReportType>('CONSULTATIONS')
  const [outputFormat, setOutputFormat] = useState<OutputFormat>('CSV')
  const [fromDate, setFromDate] = useState('')
  const [toDate, setToDate] = useState('')
  const [error, setError] = useState<string | null>(null)
  const requestExport = useRequestExport()

  const handleSubmit = async () => {
    setError(null)
    try {
      const result = await requestExport.mutateAsync({
        report_type: reportType,
        output_format: outputFormat,
        parameters: {
          from_date: fromDate || undefined,
          to_date: toDate || undefined,
        },
      })
      onJobCreated(result.job_id)
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Exportar Relatório"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancelar</Button>
          <Button
            onClick={handleSubmit}
            loading={requestExport.isPending}
            icon={<Download className="w-4 h-4" />}
          >
            Gerar Exportação
          </Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        <Select
          label="Tipo de Relatório"
          value={reportType}
          onChange={(e) => setReportType(e.target.value as ReportType)}
          options={[
            { value: 'CONSULTATIONS', label: 'Consultas' },
            { value: 'PATIENTS', label: 'Pacientes' },
            { value: 'DOCTORS', label: 'Médicos' },
            { value: 'PRESCRIPTIONS', label: 'Prescrições' },
            { value: 'FULL_SYSTEM', label: 'Relatório Completo do Sistema' },
          ]}
        />
        <Select
          label="Formato de Saída"
          value={outputFormat}
          onChange={(e) => setOutputFormat(e.target.value as OutputFormat)}
          options={[
            { value: 'CSV', label: 'CSV (Tabela)' },
            { value: 'XLSX', label: 'XLSX (Planilha Excel)' },
            { value: 'PDF', label: 'PDF' },
            { value: 'JSON', label: 'JSON' },
          ]}
        />
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-300">Data inicial</label>
            <input
              type="date"
              value={fromDate}
              onChange={(e) => setFromDate(e.target.value)}
              className="w-full h-10 bg-slate-900 border border-slate-700/80 rounded-xl px-3 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
            />
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-slate-300">Data final</label>
            <input
              type="date"
              value={toDate}
              onChange={(e) => setToDate(e.target.value)}
              className="w-full h-10 bg-slate-900 border border-slate-700/80 rounded-xl px-3 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50"
            />
          </div>
        </div>
        <Alert variant="info">
          A exportação é processada em background pelo Celery. O arquivo ficará disponível para
          download assim que concluído.
        </Alert>
      </div>
    </Modal>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────
export function ReportsPage() {
  const [exportOpen, setExportOpen] = useState(false)
  const [exportJobs, setExportJobs] = useState<string[]>([])

  const { data: summary, isLoading: summaryLoading, refetch: refetchSummary } = useDashboardSummary()
  const { data: consultations, isLoading: consultLoading } = useConsultationsReport()

  // Build chart data from API response
  const chartData = (consultations?.data ?? []).slice(0, 14).reverse().map((d: any) => ({
    date: formatDate(d.date, 'dd/MM'),
    consultas: d.consultations,
  }))

  const handleJobCreated = (jobId: string) => {
    setExportJobs((prev) => [jobId, ...prev])
  }

  return (
    <div>
      <PageHeader
        title="Relatórios"
        description="Análise de dados clínicos e operacionais"
        action={
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              icon={<RefreshCw className="w-3.5 h-3.5" />}
              onClick={() => refetchSummary()}
            >
              Atualizar
            </Button>
            <Button
              icon={<Download className="w-4 h-4" />}
              onClick={() => setExportOpen(true)}
            >
              Exportar
            </Button>
          </div>
        }
      />

      {/* Summary stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <StatCard
          label="Consultas hoje"
          value={summaryLoading ? '…' : (summary?.consultations_today ?? 0)}
          icon={<Calendar className="w-5 h-5" />}
          color="brand"
        />
        <StatCard
          label="Novos pacientes este mês"
          value={summaryLoading ? '…' : (summary?.new_patients_this_month ?? 0)}
          icon={<Users className="w-5 h-5" />}
          color="violet"
        />
        <StatCard
          label="Cancelamentos hoje"
          value={summaryLoading ? '…' : (summary?.cancellations_today ?? 0)}
          icon={<AlertCircle className="w-5 h-5" />}
          color="amber"
        />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6 mb-8">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-200">Consultas por Dia</h3>
                <p className="text-xs text-slate-500 mt-0.5">Últimos 14 dias</p>
              </div>
              <BarChart3 className="w-4 h-4 text-brand-400" />
            </div>
          </CardHeader>
          <CardBody className="pt-2">
            {consultLoading ? (
              <div className="h-48 flex items-center justify-center">
                <Spinner />
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-48 flex items-center justify-center text-sm text-slate-600">
                Nenhum dado disponível ainda.
                <br />Os eventos são processados em tempo real via RabbitMQ.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_COLORS.brand} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={CHART_COLORS.brand} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area
                    type="monotone"
                    dataKey="consultas"
                    name="consultas"
                    stroke={CHART_COLORS.brand}
                    strokeWidth={2}
                    fill="url(#grad)"
                    dot={{ fill: CHART_COLORS.brand, r: 3, strokeWidth: 0 }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        {/* Info card */}
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-200">Como funciona</h3>
          </CardHeader>
          <CardBody>
            <div className="space-y-4">
              {[
                {
                  icon: <BarChart3 className="w-4 h-4 text-brand-400" />,
                  title: 'Dados em tempo real',
                  desc: 'Estatísticas atualizadas via eventos RabbitMQ conforme consultas são agendadas.',
                },
                {
                  icon: <Download className="w-4 h-4 text-violet-400" />,
                  title: 'Exportação assíncrona',
                  desc: 'CSV e PDF são gerados pelo worker Celery. Clique em "Exportar" e acompanhe o status.',
                },
                {
                  icon: <Clock className="w-4 h-4 text-amber-400" />,
                  title: 'Atualização automática',
                  desc: 'O dashboard se atualiza a cada 60 segundos automaticamente.',
                },
              ].map((item) => (
                <div key={item.title} className="flex gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-800/60 flex items-center justify-center flex-shrink-0">
                    {item.icon}
                  </div>
                  <div>
                    <p className="text-sm font-medium text-slate-200">{item.title}</p>
                    <p className="text-xs text-slate-500 mt-0.5">{item.desc}</p>
                  </div>
                </div>
              ))}
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Export jobs */}
      {exportJobs.length > 0 && (
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <FileText className="w-4 h-4 text-brand-400" />
              Exportações em andamento
            </h3>
          </CardHeader>
          <CardBody className="space-y-3">
            {exportJobs.map((jobId) => (
              <ExportJobStatus key={jobId} jobId={jobId} />
            ))}
          </CardBody>
        </Card>
      )}

      <ExportModal
        open={exportOpen}
        onClose={() => setExportOpen(false)}
        onJobCreated={handleJobCreated}
      />
    </div>
  )
}
