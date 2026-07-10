import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { TokenPayload, User, Role } from '@/types'
import { tokenStorage } from '@/api/client'
import { authApi } from '@/api/services'

// Simple JWT decode without external lib dependency
function decodeJwt(token: string): TokenPayload | null {
  try {
    const base64 = token.split('.')[1]
    const padded = base64 + '='.repeat((4 - base64.length % 4) % 4)
    return JSON.parse(atob(padded)) as TokenPayload
  } catch {
    return null
  }
}

interface AuthState {
  user: User | null
  role: Role | null
  isAuthenticated: boolean
  isLoading: boolean

  // Actions
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  loadUser: () => Promise<void>
  setUser: (user: User) => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      role: null,
      isAuthenticated: false,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true })
        try {
          const tokens = await authApi.login({ email, password })
          tokenStorage.set(tokens)

          const payload = decodeJwt(tokens.access_token)
          const user = await authApi.me()

          set({
            user,
            role: payload?.role ?? null,
            isAuthenticated: true,
            isLoading: false,
          })
        } catch (err) {
          set({ isLoading: false })
          throw err
        }
      },

      logout: async () => {
        try {
          const refreshToken = tokenStorage.getRefresh()
          if (refreshToken) await authApi.logout(refreshToken)
        } finally {
          tokenStorage.clear()
          set({ user: null, role: null, isAuthenticated: false })
        }
      },

      loadUser: async () => {
        const token = tokenStorage.getAccess()
        if (!token) {
          set({ isAuthenticated: false, isLoading: false })
          return
        }
        const payload = decodeJwt(token)
        if (!payload || payload.exp * 1000 < Date.now()) {
          set({ isAuthenticated: false, isLoading: false })
          return
        }
        try {
          set({ isLoading: true })
          const user = await authApi.me()
          set({ user, role: payload.role, isAuthenticated: true, isLoading: false })
        } catch {
          tokenStorage.clear()
          set({ user: null, role: null, isAuthenticated: false, isLoading: false })
        }
      },

      setUser: (user) => set({ user }),
    }),
    {
      name: 'promptuario-auth',
      partialize: (state) => ({ user: state.user, role: state.role, isAuthenticated: state.isAuthenticated }),
    }
  )
)

// Role helpers
export const useRole = () => useAuthStore((s) => s.role)
export const useUser = () => useAuthStore((s) => s.user)
export const useIsAdmin = () => useAuthStore((s) => s.role === 'ADMIN')
export const useIsDoctor = () => useAuthStore((s) => s.role === 'DOCTOR')
export const useIsAttendant = () => useAuthStore((s) => s.role === 'ATTENDANT')
export const useIsPatient = () => useAuthStore((s) => s.role === 'PATIENT')

export const hasRole = (role: Role | null, ...allowedRoles: Role[]): boolean =>
  role !== null && allowedRoles.includes(role)
