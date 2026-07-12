import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, Users, UserRound, Calendar, FileText,
  BarChart3, Brain, Settings, LogOut, ChevronRight,
  Stethoscope, Shield, Activity, UserCircle,
} from 'lucide-react'
import { cn, ROLE_LABELS } from '@/utils'
import { useAuthStore, useRole } from '@/store/auth.store'
import { initials } from '@/utils'

interface NavItem {
  label: string
  href: string
  icon: React.ReactNode
  roles: string[]
  badge?: string
}

const NAV_ITEMS: NavItem[] = [
  {
    label: 'Dashboard',
    href: '/dashboard',
    icon: <LayoutDashboard className="w-4 h-4" />,
    roles: ['ADMIN', 'DOCTOR', 'ATTENDANT', 'PATIENT'],
  },
  {
    label: 'Pacientes',
    href: '/patients',
    icon: <UserRound className="w-4 h-4" />,
    roles: ['ADMIN', 'DOCTOR', 'ATTENDANT'],
  },
  {
    label: 'Consultas',
    href: '/appointments',
    icon: <Calendar className="w-4 h-4" />,
    roles: ['ADMIN', 'DOCTOR', 'ATTENDANT', 'PATIENT'],
  },
  {
    label: 'Prontuários',
    href: '/records',
    icon: <FileText className="w-4 h-4" />,
    roles: ['ADMIN', 'DOCTOR', 'PATIENT'],
  },
  {
    label: 'Análise IA',
    href: '/ai',
    icon: <Brain className="w-4 h-4" />,
    roles: ['ADMIN', 'DOCTOR'],
  },
  {
    label: 'Relatórios',
    href: '/reports',
    icon: <BarChart3 className="w-4 h-4" />,
    roles: ['ADMIN', 'DOCTOR'],
  },
  {
    label: 'Minha Saúde',
    href: '/my-health',
    icon: <Activity className="w-4 h-4" />,
    roles: ['PATIENT'],
  },
  {
    label: 'Usuários',
    href: '/admin/users',
    icon: <Shield className="w-4 h-4" />,
    roles: ['ADMIN'],
  },
  {
    label: 'Auditoria',
    href: '/admin/audit',
    icon: <Activity className="w-4 h-4" />,
    roles: ['ADMIN'],
  },
]

export function Sidebar() {
  const role = useRole()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const visibleItems = NAV_ITEMS.filter(
    (item) => role && item.roles.includes(role)
  )

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <aside className="w-64 h-screen flex flex-col bg-slate-950 border-r border-slate-800/60 fixed left-0 top-0 z-30">
      {/* Logo */}
      <div className="px-6 py-5 border-b border-slate-800/60">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center shadow-glow-sm">
            <Activity className="w-4 h-4 text-white" />
          </div>
          <div>
            <span className="font-display font-bold text-slate-100 text-base tracking-tight">
              PROMPTUÁRIO
            </span>
            <div className="text-[10px] text-brand-400 font-medium tracking-widest uppercase">
              Sistema EHR
            </div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {visibleItems.map((item) => (
          <NavLink
            key={item.href}
            to={item.href}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 group',
                isActive
                  ? 'bg-brand-500/15 text-brand-300 shadow-glow-sm'
                  : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/60'
              )
            }
          >
            {({ isActive }) => (
              <>
                <span className={cn(
                  'transition-colors',
                  isActive ? 'text-brand-400' : 'text-slate-600 group-hover:text-slate-400'
                )}>
                  {item.icon}
                </span>
                <span className="flex-1">{item.label}</span>
                {isActive && (
                  <ChevronRight className="w-3 h-3 text-brand-500 opacity-60" />
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User Section */}
      <div className="border-t border-slate-800/60 p-3 space-y-2">
        <NavLink
          to="/profile"
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150',
              isActive
                ? 'bg-brand-500/15 text-brand-300'
                : 'text-slate-500 hover:text-slate-300 hover:bg-slate-800/60'
            )
          }
        >
          <div className="w-8 h-8 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center flex-shrink-0">
            <span className="text-xs font-bold text-brand-300">
              {user ? initials(user.full_name) : '?'}
            </span>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-200 truncate">
              {user?.full_name ?? '—'}
            </p>
            <p className="text-[10px] text-slate-500 truncate">
              {role ? ROLE_LABELS[role] : ''}
            </p>
          </div>
        </NavLink>

        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-xl text-sm text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-all duration-150"
        >
          <LogOut className="w-4 h-4" />
          Sair
        </button>
      </div>
    </aside>
  )
}