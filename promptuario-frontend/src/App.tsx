import { lazy, Suspense, useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useAuthStore } from '@/store/auth.store'
import { AppShell, AuthGuard, RoleGuard } from '@/components/layout/AppShell'
import { PageLoader } from '@/components/ui'

// Lazy-loaded pages
const LoginPage = lazy(() =>
  import('@/pages/auth/LoginPage').then((m) => ({ default: m.LoginPage }))
)
const DashboardPage = lazy(() =>
  import('@/pages/dashboard/DashboardPage').then((m) => ({ default: m.DashboardPage }))
)
const PatientListPage = lazy(() =>
  import('@/pages/patients/PatientListPage').then((m) => ({ default: m.PatientListPage }))
)
const PatientDetailPage = lazy(() =>
  import('@/pages/patients/PatientDetailPage').then((m) => ({ default: m.PatientDetailPage }))
)
const RecordsPage = lazy(() =>
  import('@/pages/records/RecordsPage').then((m) => ({ default: m.RecordsPage }))
)
const AppointmentsPage = lazy(() =>
  import('@/pages/appointments/AppointmentsPage').then((m) => ({ default: m.AppointmentsPage }))
)
const ReportsPage = lazy(() =>
  import('@/pages/reports/ReportsPage').then((m) => ({ default: m.ReportsPage }))
)
const UserManagementPage = lazy(() =>
  import('@/pages/admin/UserManagementPage').then((m) => ({ default: m.UserManagementPage }))
)

// React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: (failureCount, error: any) => {
        // Don't retry on auth errors
        if (error?.response?.status === 401 || error?.response?.status === 403) return false
        return failureCount < 2
      },
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: false,
    },
  },
})

// Bootstrap component — loads user on app start
function AppBootstrap() {
  const { loadUser, isAuthenticated } = useAuthStore()

  useEffect(() => {
    loadUser()
  }, [loadUser])

  return null
}

function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Public */}
        <Route path="/login" element={<LoginPage />} />

        {/* Protected — requires auth */}
        <Route element={<AuthGuard />}>
          <Route element={<AppShell />}>

            {/* All roles */}
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/appointments" element={<AppointmentsPage />} />

            {/* ADMIN, DOCTOR, ATTENDANT only */}
            <Route element={<RoleGuard allowedRoles={['ADMIN', 'DOCTOR', 'ATTENDANT']} />}>
              <Route path="/patients" element={<PatientListPage />} />
              <Route path="/patients/:id" element={<PatientDetailPage />} />
            </Route>

            {/* ADMIN, DOCTOR, PATIENT (own records) */}
            <Route element={<RoleGuard allowedRoles={['ADMIN', 'DOCTOR', 'PATIENT']} />}>
              <Route path="/records" element={<RecordsPage />} />
              <Route path="/records/:recordId" element={<RecordsPage />} />
              <Route path="/patients/:patientId/records" element={<RecordsPage />} />
            </Route>

            {/* ADMIN, DOCTOR only */}
            <Route element={<RoleGuard allowedRoles={['ADMIN', 'DOCTOR']} />}>
              <Route path="/reports" element={<ReportsPage />} />
            </Route>

            {/* ADMIN only */}
            <Route element={<RoleGuard allowedRoles={['ADMIN']} />}>
              <Route path="/admin/users" element={<UserManagementPage />} />
            </Route>

          </Route>
        </Route>

        {/* Redirects */}
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={
          <div className="min-h-screen bg-slate-950 flex items-center justify-center">
            <div className="text-center">
              <div className="text-7xl font-display font-bold text-slate-800 mb-3">404</div>
              <p className="text-slate-400">Página não encontrada</p>
              <a href="/dashboard" className="mt-4 inline-block text-sm text-brand-400 hover:underline">
                Voltar ao Dashboard
              </a>
            </div>
          </div>
        } />
      </Routes>
    </Suspense>
  )
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppBootstrap />
        <AppRoutes />
      </BrowserRouter>
      {import.meta.env.DEV && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  )
}
