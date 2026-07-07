import { Outlet, Navigate, useLocation } from 'react-router-dom'
import { Bell, Search } from 'lucide-react'
import { Sidebar } from './Sidebar'
import { useAuthStore, hasRole } from '@/store/auth.store'
import { cn } from '@/utils'
import type { Role } from '@/types'

// ─── Auth Guard ───────────────────────────────────────────────────────────
export function AuthGuard() {
  const { isAuthenticated } = useAuthStore()
  const location = useLocation()

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <Outlet />
}

// ─── Role Guard ───────────────────────────────────────────────────────────
interface RoleGuardProps {
  allowedRoles: Role[]
}

export function RoleGuard({ allowedRoles }: RoleGuardProps) {
  const role = useAuthStore((s) => s.role)

  if (!hasRole(role, ...allowedRoles)) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-slate-950">
        <div className="text-center">
          <div className="text-6xl font-display font-bold text-slate-800 mb-3">403</div>
          <p className="text-slate-400 text-sm">Você não tem permissão para acessar esta página.</p>
        </div>
      </div>
    )
  }
  return <Outlet />
}

// ─── Top Bar ───────────────────────────────────────────────────────────────
function TopBar({ title }: { title?: string }) {
  return (
    <header className="h-14 border-b border-slate-800/60 bg-slate-950/80 backdrop-blur-sm flex items-center justify-between px-6 sticky top-0 z-20">
      <div className="flex-1" />
      <div className="flex items-center gap-2">
        <button className="p-2 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800/60 transition-colors">
          <Bell className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}

// ─── App Shell ─────────────────────────────────────────────────────────────
export function AppShell() {
  return (
    <div className="min-h-screen bg-slate-950 flex">
      <Sidebar />
      <div className="flex-1 ml-64 flex flex-col min-h-screen">
        <TopBar />
        <main className="flex-1 p-6 animate-fade-in">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

// ─── Page Header ───────────────────────────────────────────────────────────
interface PageHeaderProps {
  title: string
  description?: string
  action?: React.ReactNode
  breadcrumb?: { label: string; href?: string }[]
}

export function PageHeader({ title, description, action, breadcrumb }: PageHeaderProps) {
  return (
    <div className="mb-8">
      {breadcrumb && breadcrumb.length > 0 && (
        <nav className="flex items-center gap-1.5 text-xs text-slate-500 mb-3">
          {breadcrumb.map((crumb, i) => (
            <span key={i} className="flex items-center gap-1.5">
              {i > 0 && <span>/</span>}
              <span className={cn(i === breadcrumb.length - 1 ? 'text-slate-300' : 'hover:text-slate-300 cursor-pointer')}>
                {crumb.label}
              </span>
            </span>
          ))}
        </nav>
      )}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold font-display text-slate-100">{title}</h1>
          {description && (
            <p className="text-sm text-slate-500 mt-1">{description}</p>
          )}
        </div>
        {action && <div className="flex-shrink-0">{action}</div>}
      </div>
    </div>
  )
}
