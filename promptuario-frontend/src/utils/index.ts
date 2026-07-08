import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow, parseISO, differenceInYears } from 'date-fns'
import { ptBR } from 'date-fns/locale'

// Tailwind class merger
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// ─── Date Formatters ───────────────────────────────────────────────────────
export function formatDate(date: string | null | undefined, pattern = 'dd/MM/yyyy'): string {
  if (!date) return '—'
  try {
    return format(parseISO(date), pattern, { locale: ptBR })
  } catch {
    return '—'
  }
}

export function formatDateTime(date: string | null | undefined): string {
  return formatDate(date, "dd/MM/yyyy 'às' HH:mm")
}

export function formatRelative(date: string | null | undefined): string {
  if (!date) return '—'
  try {
    return formatDistanceToNow(parseISO(date), { addSuffix: true, locale: ptBR })
  } catch {
    return '—'
  }
}

export function calculateAge(dateOfBirth: string | null): number | null {
  if (!dateOfBirth) return null
  try {
    return differenceInYears(new Date(), parseISO(dateOfBirth))
  } catch {
    return null
  }
}

// ─── Text Formatters ───────────────────────────────────────────────────────
export function formatCPF(cpf: string | null | undefined): string {
  if (!cpf) return '—'
  return cpf.replace(/\D/g, '').replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4')
}

export function formatPhone(phone: string | null | undefined): string {
  if (!phone) return '—'
  return phone
}

export function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((n) => n[0].toUpperCase())
    .join('')
}

export function truncate(str: string, maxLen: number): string {
  return str.length > maxLen ? str.slice(0, maxLen) + '…' : str
}

// ─── Role Labels ───────────────────────────────────────────────────────────
export const ROLE_LABELS: Record<string, string> = {
  ADMIN: 'Administrador',
  DOCTOR: 'Médico',
  ATTENDANT: 'Atendente',
  PATIENT: 'Paciente',
}

export const ROLE_COLORS: Record<string, string> = {
  ADMIN: 'bg-violet-500/15 text-violet-300 ring-violet-500/20',
  DOCTOR: 'bg-brand-500/15 text-brand-300 ring-brand-500/20',
  ATTENDANT: 'bg-sky-500/15 text-sky-300 ring-sky-500/20',
  PATIENT: 'bg-slate-500/15 text-slate-300 ring-slate-500/20',
}

export const STATUS_LABELS: Record<string, string> = {
  SCHEDULED: 'Agendada',
  CONFIRMED: 'Confirmada',
  COMPLETED: 'Concluída',
  CANCELLED: 'Cancelada',
  NO_SHOW: 'Não compareceu',
}

export const STATUS_COLORS: Record<string, string> = {
  SCHEDULED: 'bg-sky-500/15 text-sky-300',
  CONFIRMED: 'bg-brand-500/15 text-brand-300',
  COMPLETED: 'bg-emerald-500/15 text-emerald-300',
  CANCELLED: 'bg-rose-500/15 text-rose-300',
  NO_SHOW: 'bg-amber-500/15 text-amber-300',
}

export const SEVERITY_COLORS: Record<string, string> = {
  MILD: 'bg-amber-500/15 text-amber-300',
  MODERATE: 'bg-orange-500/15 text-orange-300',
  SEVERE: 'bg-rose-500/15 text-rose-300',
}

export const RISK_COLORS: Record<string, string> = {
  LOW: 'text-emerald-400',
  MEDIUM: 'text-amber-400',
  HIGH: 'text-orange-400',
  CRITICAL: 'text-rose-400',
}

// ─── File Download ─────────────────────────────────────────────────────────
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

// ─── Axios error extractor ─────────────────────────────────────────────────
export function getErrorMessage(error: unknown): string {
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as { response?: { data?: { detail?: string } } }
    return axiosError.response?.data?.detail ?? 'Erro desconhecido'
  }
  return 'Erro ao processar requisição'
}
