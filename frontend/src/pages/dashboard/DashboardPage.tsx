import { useState } from 'react'
import {
  Users, Calendar, FileText, TrendingUp,
  Brain, Activity, Clock, ArrowRight,
  CheckCircle, AlertCircle, UserRound,
} from 'lucide-react'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, BarChart, Bar, CartesianGrid,
} from 'recharts'
import { useAuthStore, useIsDoctor, useIsAdmin, useIsPatient } from '@/store/auth.store'
import { useDashboardSummary, useAppointments, usePatients } from '@/hooks'
import { PageHeader } from '@/components/layout/AppShell'
import {
  StatCard, Card, CardHeader, CardBody,
  Badge, PageLoader, EmptyState,
} from '@/components/ui'
import { formatDateTime, formatRelative, STATUS_LABELS, STATUS_COLORS, cn } from '@/utils'
import { Link } from 'react-router-dom'

// Mock chart data – in production replace with real report endpoint data
const consultationTrend = [
  { day: 'Seg', consultas: 8 },
  { day: 'Ter', consultas: 12 },
  { day: 'Qua', consultas: 6 },
  { day: 'Qui', consultas: 15 },
  { day: 'Sex', consultas: 10 },
  { day: 'Sáb', consultas: 4 },
  { day: 'Dom', consultas: 2 },
]

const specialtyData = [
  { name: 'Clínica Geral', value: 40 },
  { name: 'Cardiologia', value: 18 },
  { name: 'Ortopedia', value: 15 },
  { name: 'Pediatria', value: 12 },
  { name: 'Outros', value: 15 },
]

const CHART_COLORS = {
  brand: '#1ab0a4',
  violet: '#8b5cf6',
  amber: '#f59e0b',
}

// Custom tooltip for recharts
function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl px-3 py-2 text-xs shadow-modal">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} className="font-semibold text-slate-200">
          {p.value} {p.name}
        </p>
      ))}
    </div>
  )
}

// Admin / Doctor dashboard
function AdminDoctorDashboard() {
  const { data: summary, isLoading: summaryLoading } = useDashboardSummary()
  const { data: appointments, isLoading: apptLoading } = useAppointments({
    page: 1, size: 5, status: 'SCHEDULED',
  })

  return (
    <div className="space-y-8">
      {/* Stats row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Consultas hoje"
          value={summaryLoading ? '—' : (summary?.consultations_today ?? 0)}
          icon={<Calendar className="w-5 h-5" />}
          color="brand"
          trend={{ value: '+12%', up: true }}
        />
        <StatCard
          label="Novos pacientes este mês"
          value={summaryLoading ? '—' : (summary?.new_patients_this_month ?? 0)}
          icon={<UserRound className="w-5 h-5" />}
          color="violet"
          trend={{ value: '+5%', up: true }}
        />
        <StatCard
          label="Cancelamentos hoje"
          value={summaryLoading ? '—' : (summary?.cancellations_today ?? 0)}
          icon={<AlertCircle className="w-5 h-5" />}
          color="amber"
        />
        <StatCard
          label="Prontuários registrados"
          value="—"
          icon={<FileText className="w-5 h-5" />}
          color="brand"
        />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Consultation trend */}
        <Card className="xl:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold text-slate-200">Consultas esta semana</h3>
                <p className="text-xs text-slate-500 mt-0.5">Distribuição diária</p>
              </div>
              <TrendingUp className="w-4 h-4 text-brand-400" />
            </div>
          </CardHeader>
          <CardBody className="pt-2">
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={consultationTrend}>
                <defs>
                  <linearGradient id="grad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor={CHART_COLORS.brand} stopOpacity={0.25} />
                    <stop offset="95%" stopColor={CHART_COLORS.brand} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="day" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
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
          </CardBody>
        </Card>

        {/* Specialty breakdown */}
        <Card>
          <CardHeader>
            <div>
              <h3 className="text-sm font-semibold text-slate-200">Por especialidade</h3>
              <p className="text-xs text-slate-500 mt-0.5">Últimos 30 dias</p>
            </div>
          </CardHeader>
          <CardBody className="pt-2">
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={specialtyData} layout="vertical">
                <XAxis type="number" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} width={80} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" name="consultas" fill={CHART_COLORS.brand} radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardBody>
        </Card>
      </div>

      {/* Recent appointments */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-200">Próximas consultas</h3>
              <p className="text-xs text-slate-500 mt-0.5">Agendadas e confirmadas</p>
            </div>
            <Link
              to="/appointments"
              className="flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 transition-colors"
            >
              Ver todas <ArrowRight className="w-3 h-3" />
            </Link>
          </div>
        </CardHeader>
        <CardBody className="p-0">
          {apptLoading ? (
            <PageLoader />
          ) : !appointments?.items.length ? (
            <EmptyState
              icon={<Calendar className="w-7 h-7" />}
              title="Nenhuma consulta agendada"
            />
          ) : (
            <div className="divide-y divide-slate-800/60">
              {appointments.items.map((appt) => (
                <div
                  key={appt.id}
                  className="flex items-center justify-between px-6 py-3 hover:bg-slate-800/30 transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-brand-500/10 flex items-center justify-center">
                      <Calendar className="w-4 h-4 text-brand-400" />
                    </div>
                    <div>
                      <p className="text-sm font-medium text-slate-200">
                        {appt.specialty ?? appt.appointment_type}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatDateTime(appt.scheduled_at)}
                      </p>
                    </div>
                  </div>
                  <Badge className={STATUS_COLORS[appt.status]}>
                    {STATUS_LABELS[appt.status]}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

// Patient dashboard — simplified view
function PatientDashboard() {
  const { user } = useAuthStore()
  const { data: appointments } = useAppointments({ page: 1, size: 3 })

  return (
    <div className="space-y-6">
      {/* Welcome card */}
      <Card className="bg-gradient-to-br from-brand-500/10 to-violet-500/5 border-brand-500/20">
        <CardBody className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-brand-500/20 border border-brand-500/30 flex items-center justify-center flex-shrink-0">
            <Activity className="w-7 h-7 text-brand-400" />
          </div>
          <div>
            <h2 className="text-lg font-bold font-display text-slate-100">
              Olá, {user?.full_name.split(' ')[0]}!
            </h2>
            <p className="text-sm text-slate-400 mt-0.5">
              Acompanhe suas consultas e prontuários aqui.
            </p>
          </div>
        </CardBody>
      </Card>

      {/* Quick actions */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[
          { label: 'Minhas consultas', href: '/appointments', icon: <Calendar className="w-5 h-5" />, color: 'brand' },
          { label: 'Meu prontuário', href: '/records', icon: <FileText className="w-5 h-5" />, color: 'violet' },
          { label: 'Histórico', href: '/records', icon: <Clock className="w-5 h-5" />, color: 'amber' },
        ].map((item) => (
          <Link key={item.label} to={item.href}>
            <Card hover className="p-5">
              <div className={cn(
                'w-10 h-10 rounded-xl flex items-center justify-center mb-3',
                item.color === 'brand' ? 'bg-brand-500/15 text-brand-400' :
                item.color === 'violet' ? 'bg-violet-500/15 text-violet-400' :
                'bg-amber-500/15 text-amber-400'
              )}>
                {item.icon}
              </div>
              <p className="text-sm font-semibold text-slate-200">{item.label}</p>
              <ArrowRight className="w-3 h-3 text-slate-600 mt-1" />
            </Card>
          </Link>
        ))}
      </div>

      {/* Recent appointments */}
      <Card>
        <CardHeader>
          <h3 className="text-sm font-semibold text-slate-200">Minhas consultas recentes</h3>
        </CardHeader>
        <CardBody className="p-0">
          {!appointments?.items.length ? (
            <EmptyState
              icon={<Calendar className="w-7 h-7" />}
              title="Nenhuma consulta encontrada"
            />
          ) : (
            <div className="divide-y divide-slate-800/60">
              {appointments.items.map((appt) => (
                <div key={appt.id} className="flex items-center justify-between px-6 py-3">
                  <div>
                    <p className="text-sm font-medium text-slate-200">
                      {appt.specialty ?? appt.appointment_type}
                    </p>
                    <p className="text-xs text-slate-500">{formatDateTime(appt.scheduled_at)}</p>
                  </div>
                  <Badge className={STATUS_COLORS[appt.status]}>
                    {STATUS_LABELS[appt.status]}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

export function DashboardPage() {
  const { user, role } = useAuthStore()
  const isPatient = useIsPatient()

  return (
    <div>
      <PageHeader
        title={isPatient ? 'Meu Portal' : 'Dashboard'}
        description={
          isPatient
            ? `Bem-vindo ao seu portal de saúde`
            : `Visão geral operacional do sistema`
        }
      />
      {isPatient ? <PatientDashboard /> : <AdminDoctorDashboard />}
    </div>
  )
}
