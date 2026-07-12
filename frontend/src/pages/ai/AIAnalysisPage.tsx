import { useMemo, useState } from 'react'
import {
  Brain, Play, RefreshCw, Activity, ShieldAlert,
  FileText, CheckCircle2, Loader2,
} from 'lucide-react'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Select,
  Input, Textarea, Alert, Badge, EmptyState,
} from '@/components/ui'
import {
  useRequestAnalysis, useAnalysisJob, useRecordAnalyses,
} from '@/hooks'
import type { AnalysisType, AnalysisJob } from '@/types'
import { cn, formatDateTime, formatRelative, getErrorMessage, RISK_COLORS } from '@/utils'

const ANALYSIS_OPTIONS: Array<{ value: AnalysisType; label: string }> = [
  { value: 'SYMPTOM_ANALYSIS', label: 'Análise de Sintomas' },
  { value: 'DRUG_INTERACTION_CHECK', label: 'Interações Medicamentosas' },
  { value: 'CLINICAL_SUMMARY', label: 'Resumo Clínico' },
]

function toLabel(value: string) {
  return value
    .replace(/_/g, ' ')
    .toLowerCase()
    .replace(/\b\w/g, (m) => m.toUpperCase())
}

function statusClass(status: string) {
  if (status === 'COMPLETED') return 'bg-emerald-500/15 text-emerald-300 ring-emerald-500/20'
  if (status === 'FAILED') return 'bg-rose-500/15 text-rose-300 ring-rose-500/20'
  return 'bg-amber-500/15 text-amber-300 ring-amber-500/20'
}

function parseContext(text: string): { value?: object; error?: string } {
  const trimmed = text.trim()
  if (!trimmed) return { value: {} }
  try {
    const parsed = JSON.parse(trimmed)
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      return { value: parsed as object }
    }
    return { error: 'O contexto deve ser um objeto JSON (ex.: {"sintomas": "..."}).' }
  } catch {
    return { error: 'JSON inválido no campo de contexto.' }
  }
}

function JobResult({ job }: { job: AnalysisJob }) {
  if (!job.result) {
    return <p className="text-xs text-slate-500">Sem resultado disponível ainda.</p>
  }

  const entries = Object.entries(job.result)
  if (entries.length === 0) {
    return <p className="text-xs text-slate-500">Resultado vazio.</p>
  }

  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => {
        const asArray = Array.isArray(value)
        const asObject = !!value && typeof value === 'object' && !Array.isArray(value)

        return (
          <div key={key} className="rounded-xl border border-slate-800/70 bg-slate-950/60 p-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1.5">{toLabel(key)}</p>
            {asArray ? (
              <ul className="space-y-1">
                {(value as unknown[]).map((item, i) => (
                  <li key={i} className="text-sm text-slate-300">• {String(item)}</li>
                ))}
              </ul>
            ) : asObject ? (
              <pre className="text-xs text-slate-300 whitespace-pre-wrap break-words font-mono">
                {JSON.stringify(value, null, 2)}
              </pre>
            ) : (
              <p className="text-sm text-slate-300">{String(value)}</p>
            )}
          </div>
        )
      })}
    </div>
  )
}

export function AIAnalysisPage() {
  const requestAnalysis = useRequestAnalysis()

  const [analysisType, setAnalysisType] = useState<AnalysisType>('SYMPTOM_ANALYSIS')
  const [patientId, setPatientId] = useState('')
  const [recordId, setRecordId] = useState('')
  const [contextText, setContextText] = useState('')
  const [formError, setFormError] = useState<string | null>(null)

  const [activeJobId, setActiveJobId] = useState('')
  const [historyRecordInput, setHistoryRecordInput] = useState('')
  const [historyRecordId, setHistoryRecordId] = useState('')

  const { data: activeJob, isFetching: activeJobFetching, refetch: refetchActiveJob } = useAnalysisJob(activeJobId, !!activeJobId)
  const {
    data: analysesByRecord,
    isFetching: analysesFetching,
    refetch: refetchAnalyses,
  } = useRecordAnalyses(historyRecordId)

  const statusSummary = useMemo(() => {
    const jobs = analysesByRecord?.items ?? []
    return {
      total: jobs.length,
      completed: jobs.filter((j) => j.status === 'COMPLETED').length,
      running: jobs.filter((j) => j.status === 'PENDING' || j.status === 'RUNNING').length,
      failed: jobs.filter((j) => j.status === 'FAILED').length,
    }
  }, [analysesByRecord?.items])

  const handleSubmitAnalysis = async () => {
    setFormError(null)

    if (!patientId.trim()) {
      setFormError('Informe o ID do paciente para solicitar a análise.')
      return
    }

    const parsedContext = parseContext(contextText)
    if (parsedContext.error) {
      setFormError(parsedContext.error)
      return
    }

    try {
      const result = await requestAnalysis.mutateAsync({
        analysis_type: analysisType,
        patient_id: patientId.trim(),
        record_id: recordId.trim() || undefined,
        context: parsedContext.value,
      })
      setActiveJobId(result.job_id)
      if (recordId.trim()) {
        setHistoryRecordInput(recordId.trim())
        setHistoryRecordId(recordId.trim())
      }
    } catch (err) {
      setFormError(getErrorMessage(err))
    }
  }

  return (
    <div>
      <PageHeader
        title="Análise de IA"
        description="Solicite análises clínicas, acompanhe o processamento e revise históricos por prontuário"
        action={
          <Button
            variant="secondary"
            icon={<RefreshCw className="w-3.5 h-3.5" />}
            onClick={() => {
              if (activeJobId) refetchActiveJob()
              if (historyRecordId) refetchAnalyses()
            }}
          >
            Atualizar
          </Button>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 mb-6">
        <Card className="xl:col-span-2">
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <Brain className="w-4 h-4 text-brand-400" />
              Nova solicitação de análise
            </h3>
          </CardHeader>
          <CardBody className="space-y-4">
            {formError && <Alert variant="error">{formError}</Alert>}

            <Select
              label="Tipo de análise"
              value={analysisType}
              onChange={(e) => setAnalysisType(e.target.value as AnalysisType)}
              options={ANALYSIS_OPTIONS}
            />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="ID do paciente *"
                value={patientId}
                onChange={(e) => setPatientId(e.target.value)}
                placeholder="ex.: 7f5e1a4c-..."
              />
              <Input
                label="ID do prontuário (opcional)"
                value={recordId}
                onChange={(e) => setRecordId(e.target.value)}
                placeholder="ex.: 12f8c9ab-..."
              />
            </div>

            <Textarea
              label="Contexto adicional (JSON opcional)"
              rows={6}
              value={contextText}
              onChange={(e) => setContextText(e.target.value)}
              placeholder='{"chief_complaint":"dor torácica", "symptoms":["dispneia"]}'
            />

            <Alert variant="info">
              O processamento roda em background e o status muda automaticamente de PENDING/RUNNING para COMPLETED ou FAILED.
            </Alert>

            <div className="flex justify-end">
              <Button
                icon={<Play className="w-4 h-4" />}
                loading={requestAnalysis.isPending}
                onClick={handleSubmitAnalysis}
              >
                Solicitar análise
              </Button>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
              <FileText className="w-4 h-4 text-violet-400" />
              Buscar histórico por prontuário
            </h3>
          </CardHeader>
          <CardBody className="space-y-4">
            <Input
              label="ID do prontuário"
              value={historyRecordInput}
              onChange={(e) => setHistoryRecordInput(e.target.value)}
              placeholder="ex.: 12f8c9ab-..."
            />

            <Button
              className="w-full"
              variant="outline"
              icon={<Activity className="w-4 h-4" />}
              onClick={() => setHistoryRecordId(historyRecordInput.trim())}
              disabled={!historyRecordInput.trim()}
            >
              Carregar análises
            </Button>

            <div className="grid grid-cols-2 gap-3 pt-1">
              <div className="rounded-xl border border-slate-800/70 bg-slate-950/50 p-3">
                <p className="text-xs text-slate-500">Total</p>
                <p className="text-lg font-semibold text-slate-200">{statusSummary.total}</p>
              </div>
              <div className="rounded-xl border border-slate-800/70 bg-slate-950/50 p-3">
                <p className="text-xs text-slate-500">Concluídas</p>
                <p className="text-lg font-semibold text-emerald-400">{statusSummary.completed}</p>
              </div>
              <div className="rounded-xl border border-slate-800/70 bg-slate-950/50 p-3">
                <p className="text-xs text-slate-500">Em fila</p>
                <p className="text-lg font-semibold text-amber-400">{statusSummary.running}</p>
              </div>
              <div className="rounded-xl border border-slate-800/70 bg-slate-950/50 p-3">
                <p className="text-xs text-slate-500">Falhas</p>
                <p className="text-lg font-semibold text-rose-400">{statusSummary.failed}</p>
              </div>
            </div>
          </CardBody>
        </Card>
      </div>

      {activeJobId && (
        <Card className="mb-6">
          <CardHeader>
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Activity className="w-4 h-4 text-brand-400" />
                Job ativo
              </h3>
              <Badge className={cn('ring-1 ring-inset', activeJob ? statusClass(activeJob.status) : 'bg-slate-700 text-slate-200 ring-slate-600')} dot>
                {activeJob?.status ?? 'PENDING'}
              </Badge>
            </div>
          </CardHeader>
          <CardBody>
            {!activeJob ? (
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                {activeJobFetching ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                Carregando job {activeJobId}...
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                  <div>
                    <p className="text-xs text-slate-500">Tipo</p>
                    <p className="text-sm text-slate-200 font-medium">{toLabel(activeJob.analysis_type)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Criado</p>
                    <p className="text-sm text-slate-300">{formatDateTime(activeJob.created_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Atualização</p>
                    <p className="text-sm text-slate-300">{formatRelative(activeJob.completed_at ?? activeJob.created_at)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-500">Risco</p>
                    <p className={cn('text-sm font-semibold', activeJob.risk_level ? RISK_COLORS[activeJob.risk_level] : 'text-slate-400')}>
                      {activeJob.risk_level ?? 'Não calculado'}
                    </p>
                  </div>
                </div>

                {activeJob.status === 'FAILED' && (
                  <Alert variant="error" className="flex items-center gap-2">
                    <ShieldAlert className="w-4 h-4" />
                    A análise falhou. Revise o contexto enviado e tente novamente.
                  </Alert>
                )}

                {activeJob.status === 'COMPLETED' ? (
                  <JobResult job={activeJob} />
                ) : (
                  <Alert variant="warning" className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Processamento em andamento. O painel atualiza automaticamente.
                  </Alert>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            Histórico de análises do prontuário
          </h3>
        </CardHeader>
        <CardBody>
          {!historyRecordId ? (
            <EmptyState
              icon={<FileText className="w-7 h-7" />}
              title="Informe um prontuário"
              description="Use o campo acima para listar as análises de IA relacionadas a um record_id."
            />
          ) : analysesByRecord?.items?.length ? (
            <div className="space-y-3">
              {analysesByRecord.items.map((job) => (
                <button
                  key={job.id}
                  type="button"
                  className="w-full text-left rounded-xl border border-slate-800/70 bg-slate-950/60 p-4 hover:border-slate-700 transition-colors"
                  onClick={() => setActiveJobId(job.id)}
                >
                  <div className="flex items-center justify-between gap-3 mb-2">
                    <p className="text-sm font-medium text-slate-200">{toLabel(job.analysis_type)}</p>
                    <Badge className={cn('ring-1 ring-inset', statusClass(job.status))} dot>
                      {job.status}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                    <p className="text-slate-500">Job: <span className="text-slate-400 font-mono">{job.id}</span></p>
                    <p className="text-slate-500">Criado: <span className="text-slate-400">{formatDateTime(job.created_at)}</span></p>
                    <p className="text-slate-500">Risco: <span className={cn('font-semibold', job.risk_level ? RISK_COLORS[job.risk_level] : 'text-slate-400')}>{job.risk_level ?? 'N/A'}</span></p>
                  </div>
                </button>
              ))}
            </div>
          ) : analysesFetching ? (
            <div className="flex items-center gap-2 text-slate-400 text-sm">
              <Loader2 className="w-4 h-4 animate-spin" />
              Carregando histórico...
            </div>
          ) : (
            <EmptyState
              icon={<Brain className="w-7 h-7" />}
              title="Nenhuma análise encontrada"
              description="Esse prontuário ainda não possui jobs de IA registrados."
            />
          )}
        </CardBody>
      </Card>
    </div>
  )
}
