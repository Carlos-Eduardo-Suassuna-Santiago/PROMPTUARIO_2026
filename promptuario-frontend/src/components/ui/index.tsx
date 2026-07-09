import React from 'react'
import { cn } from '@/utils'
import { Loader2, X } from 'lucide-react'

// ─── Button ────────────────────────────────────────────────────────────────
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
}

export function Button({
  variant = 'primary', size = 'md', loading, icon, className, children, disabled, ...props
}: ButtonProps) {
  const base = 'inline-flex items-center justify-center gap-2 font-medium transition-all duration-150 rounded-xl focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-slate-950 disabled:opacity-50 disabled:cursor-not-allowed'

  const variants = {
    primary: 'bg-brand-500 hover:bg-brand-400 text-white focus:ring-brand-500 shadow-glow-sm hover:shadow-glow-brand active:scale-[0.98]',
    secondary: 'bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 focus:ring-slate-600',
    ghost: 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 focus:ring-slate-600',
    danger: 'bg-rose-500/15 hover:bg-rose-500/25 text-rose-400 border border-rose-500/20 focus:ring-rose-500',
    outline: 'border border-slate-700 hover:border-brand-500/50 text-slate-300 hover:text-brand-300 focus:ring-brand-500',
  }

  const sizes = {
    sm: 'h-8 px-3 text-xs',
    md: 'h-10 px-4 text-sm',
    lg: 'h-12 px-6 text-base',
  }

  return (
    <button
      className={cn(base, variants[variant], sizes[size], className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : icon}
      {children}
    </button>
  )
}

// ─── Badge ─────────────────────────────────────────────────────────────────
interface BadgeProps {
  children: React.ReactNode
  className?: string
  dot?: boolean
}

export function Badge({ children, className, dot }: BadgeProps) {
  return (
    <span className={cn(
      'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ring-inset',
      className
    )}>
      {dot && <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />}
      {children}
    </span>
  )
}

// ─── Input ─────────────────────────────────────────────────────────────────
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  hint?: string
  icon?: React.ReactNode
  suffix?: React.ReactNode
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, icon, suffix, className, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-slate-300">
            {label}
          </label>
        )}
        <div className="relative">
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
              {icon}
            </div>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'w-full h-10 bg-slate-900 border rounded-xl px-3 text-sm text-slate-200',
              'placeholder:text-slate-600 transition-all duration-150',
              'focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50',
              error ? 'border-rose-500/50 focus:ring-rose-500/30' : 'border-slate-700/80 hover:border-slate-600',
              icon && 'pl-9',
              suffix && 'pr-10',
              className,
            )}
            {...props}
          />
          {suffix && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500">
              {suffix}
            </div>
          )}
        </div>
        {error && <p className="text-xs text-rose-400">{error}</p>}
        {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
      </div>
    )
  }
)
Input.displayName = 'Input'

// ─── Textarea ──────────────────────────────────────────────────────────────
interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string
  error?: string
}

export const Textarea = React.forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, className, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-slate-300">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={inputId}
          className={cn(
            'w-full bg-slate-900 border rounded-xl px-3 py-2.5 text-sm text-slate-200',
            'placeholder:text-slate-600 transition-all duration-150 resize-none',
            'focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50',
            error ? 'border-rose-500/50' : 'border-slate-700/80 hover:border-slate-600',
            className,
          )}
          {...props}
        />
        {error && <p className="text-xs text-rose-400">{error}</p>}
      </div>
    )
  }
)
Textarea.displayName = 'Textarea'

// ─── Select ────────────────────────────────────────────────────────────────
interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string
  error?: string
  options: { value: string; label: string }[]
  placeholder?: string
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, options, placeholder, className, id, ...props }, ref) => {
    const inputId = id ?? label?.toLowerCase().replace(/\s+/g, '-')
    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-slate-300">
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={inputId}
          className={cn(
            'w-full h-10 bg-slate-900 border rounded-xl px-3 text-sm text-slate-200',
            'focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:border-brand-500/50',
            error ? 'border-rose-500/50' : 'border-slate-700/80 hover:border-slate-600',
            className,
          )}
          {...props}
        >
          {placeholder && <option value="">{placeholder}</option>}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} className="bg-slate-900">
              {opt.label}
            </option>
          ))}
        </select>
        {error && <p className="text-xs text-rose-400">{error}</p>}
      </div>
    )
  }
)
Select.displayName = 'Select'

// ─── Card ──────────────────────────────────────────────────────────────────
interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  onClick?: () => void
}

export function Card({ children, className, hover, onClick }: CardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        'bg-slate-900/60 backdrop-blur-sm border border-slate-800/80 rounded-2xl shadow-card',
        hover && 'cursor-pointer transition-all duration-200 hover:shadow-card-hover hover:border-slate-700',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('px-6 py-4 border-b border-slate-800/60', className)}>
      {children}
    </div>
  )
}

export function CardBody({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('p-6', className)}>{children}</div>
}

// ─── Spinner ───────────────────────────────────────────────────────────────
export function Spinner({ size = 'md', className }: { size?: 'sm' | 'md' | 'lg'; className?: string }) {
  const sizes = { sm: 'w-4 h-4', md: 'w-6 h-6', lg: 'w-8 h-8' }
  return <Loader2 className={cn('animate-spin text-brand-400', sizes[size], className)} />
}

export function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <Spinner size="lg" />
    </div>
  )
}

// ─── Empty State ───────────────────────────────────────────────────────────
interface EmptyStateProps {
  icon?: React.ReactNode
  title: string
  description?: string
  action?: React.ReactNode
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      {icon && (
        <div className="w-16 h-16 rounded-2xl bg-slate-800/60 flex items-center justify-center mb-4 text-slate-600">
          {icon}
        </div>
      )}
      <h3 className="text-base font-semibold text-slate-300 mb-1">{title}</h3>
      {description && <p className="text-sm text-slate-500 max-w-xs">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

// ─── Alert ─────────────────────────────────────────────────────────────────
interface AlertProps {
  children: React.ReactNode
  variant?: 'error' | 'warning' | 'info' | 'success'
  className?: string
}

export function Alert({ children, variant = 'error', className }: AlertProps) {
  const variants = {
    error: 'bg-rose-500/10 border-rose-500/20 text-rose-300',
    warning: 'bg-amber-500/10 border-amber-500/20 text-amber-300',
    info: 'bg-sky-500/10 border-sky-500/20 text-sky-300',
    success: 'bg-emerald-500/10 border-emerald-500/20 text-emerald-300',
  }
  return (
    <div className={cn('px-4 py-3 rounded-xl border text-sm', variants[variant], className)}>
      {children}
    </div>
  )
}

// ─── Modal ─────────────────────────────────────────────────────────────────
interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl'
  footer?: React.ReactNode
}

export function Modal({ open, onClose, title, children, size = 'md', footer }: ModalProps) {
  if (!open) return null

  const sizes = {
    sm: 'max-w-sm',
    md: 'max-w-lg',
    lg: 'max-w-2xl',
    xl: 'max-w-4xl',
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in"
        onClick={onClose}
      />
      <div className={cn(
        'relative w-full bg-slate-900 border border-slate-700/80 rounded-2xl shadow-modal',
        'animate-slide-up',
        sizes[size],
      )}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <h2 className="text-base font-semibold text-slate-100">{title}</h2>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6">{children}</div>
        {footer && (
          <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/40 rounded-b-2xl flex justify-end gap-2">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

// ─── Table ─────────────────────────────────────────────────────────────────
export function Table({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className={cn('w-full text-sm', className)}>{children}</table>
    </div>
  )
}

export function Th({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <th className={cn('text-left text-xs font-medium text-slate-500 uppercase tracking-wider px-4 py-3', className)}>
      {children}
    </th>
  )
}

export function Td({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <td className={cn('px-4 py-3 text-slate-300 border-t border-slate-800/60', className)}>
      {children}
    </td>
  )
}

// ─── Stat Card ─────────────────────────────────────────────────────────────
interface StatCardProps {
  label: string
  value: string | number
  icon: React.ReactNode
  trend?: { value: string; up: boolean }
  color?: string
}

export function StatCard({ label, value, icon, trend, color = 'brand' }: StatCardProps) {
  return (
    <Card className="p-6">
      <div className="flex items-start justify-between mb-4">
        <div className={cn(
          'w-10 h-10 rounded-xl flex items-center justify-center',
          color === 'brand' ? 'bg-brand-500/15 text-brand-400' :
          color === 'violet' ? 'bg-violet-500/15 text-violet-400' :
          color === 'amber' ? 'bg-amber-500/15 text-amber-400' :
          'bg-rose-500/15 text-rose-400'
        )}>
          {icon}
        </div>
        {trend && (
          <span className={cn('text-xs font-medium', trend.up ? 'text-emerald-400' : 'text-rose-400')}>
            {trend.up ? '↑' : '↓'} {trend.value}
          </span>
        )}
      </div>
      <p className="text-2xl font-bold font-display text-slate-100">{value}</p>
      <p className="text-xs text-slate-500 mt-1">{label}</p>
    </Card>
  )
}

// ─── Pagination ────────────────────────────────────────────────────────────
interface PaginationProps {
  page: number
  total: number
  size: number
  onChange: (page: number) => void
}

export function Pagination({ page, total, size, onChange }: PaginationProps) {
  const totalPages = Math.ceil(total / size)
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800/60">
      <p className="text-xs text-slate-500">
        Mostrando {Math.min((page - 1) * size + 1, total)}–{Math.min(page * size, total)} de {total}
      </p>
      <div className="flex gap-1">
        <Button
          variant="ghost"
          size="sm"
          disabled={page === 1}
          onClick={() => onChange(page - 1)}
        >
          ← Anterior
        </Button>
        <Button
          variant="ghost"
          size="sm"
          disabled={page === totalPages}
          onClick={() => onChange(page + 1)}
        >
          Próxima →
        </Button>
      </div>
    </div>
  )
}
