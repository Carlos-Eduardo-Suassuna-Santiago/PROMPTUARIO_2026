import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Alert } from '@/components/ui'
import { useAuthStore } from '@/store/auth.store'
import { tokenStorage } from '@/api/client'
import { authApi } from '@/api/services'
import { Spinner } from '@/components/ui'

export function OAuthCallback() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { loadUser } = useAuthStore()
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const accessToken = searchParams.get('access_token')
    const refreshToken = searchParams.get('refresh_token')
    const errorParam = searchParams.get('error')

    if (errorParam) {
      setError(errorParam === 'access_denied'
        ? 'Autenticação cancelada pelo provedor.'
        : 'Erro ao autenticar. Tente novamente.'
      )
      return
    }

    if (accessToken && refreshToken) {
      tokenStorage.set({
        access_token: accessToken,
        refresh_token: refreshToken,
        token_type: 'bearer',
        expires_in: 1800,
      })
      loadUser().then(() => {
        navigate('/dashboard', { replace: true })
      }).catch(() => {
        setError('Erro ao carregar dados do usuário. Tente novamente.')
      })
    } else {
      setError('Resposta inválida do provedor OAuth. Tente novamente.')
    }
  }, [searchParams, navigate, loadUser])

  if (error) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
        <div className="max-w-sm w-full text-center">
          <div className="w-16 h-16 rounded-2xl bg-rose-500/10 flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-rose-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-slate-100 mb-2">Falha na autenticação</h2>
          <Alert variant="error" className="mb-6 text-left">{error}</Alert>
          <button
            onClick={() => navigate('/login', { replace: true })}
            className="inline-flex items-center gap-2 px-4 py-2 bg-brand-500 hover:bg-brand-400 text-white rounded-xl text-sm font-medium transition-all"
          >
            Voltar ao login
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center">
      <div className="text-center">
        <Spinner size="lg" />
        <p className="text-slate-400 text-sm mt-4">Autenticando...</p>
      </div>
    </div>
  )
}