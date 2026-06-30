import { useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Activity, Eye, EyeOff, Lock, Mail, ArrowRight } from 'lucide-react'
import { useState } from 'react'
import { useAuthStore } from '@/store/auth.store'
import { Button, Input, Alert } from '@/components/ui'
import { getErrorMessage } from '@/utils'

const schema = z.object({
  email: z.string().email('Email inválido'),
  password: z.string().min(6, 'Mínimo 6 caracteres'),
})

type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, isAuthenticated, isLoading } = useAuthStore()
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/dashboard'

  useEffect(() => {
    if (isAuthenticated) navigate(from, { replace: true })
  }, [isAuthenticated, navigate, from])

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      email: 'admin@promptuario.health',
      password: 'Admin@12345',
    },
  })

  const onSubmit = async (data: FormValues) => {
    setError(null)
    try {
      await login(data.email, data.password)
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex">
      {/* Left panel — decorative */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden bg-slate-900">
        {/* Grid background */}
        <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-40" />
        {/* Glow */}
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-64 h-64 bg-violet-500/5 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-brand-500 flex items-center justify-center shadow-glow-brand">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <span className="font-display font-bold text-xl text-slate-100">PROMPTUÁRIO</span>
          </div>

          {/* Hero text */}
          <div>
            <h1 className="text-5xl font-bold font-display text-slate-100 leading-tight mb-4">
              Prontuário
              <br />
              <span className="text-brand-400">Eletrônico</span>
              <br />
              Inteligente
            </h1>
            <p className="text-slate-400 text-lg leading-relaxed max-w-sm">
              Plataforma distribuída de gestão clínica com análise assistida por IA, agendamentos e relatórios.
            </p>

            {/* Feature pills */}
            <div className="flex flex-wrap gap-2 mt-8">
              {['LGPD Compliant', 'JWT Auth', 'IA Clínica', 'Tempo Real'].map((f) => (
                <span key={f} className="px-3 py-1 bg-slate-800/80 border border-slate-700/60 rounded-full text-xs text-slate-400">
                  {f}
                </span>
              ))}
            </div>
          </div>

          {/* Footer */}
          <p className="text-xs text-slate-600">© 2026 PROMPTUÁRIO · Versão 1.0.0</p>
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm animate-slide-up">
          {/* Mobile logo */}
          <div className="flex lg:hidden items-center gap-2 mb-10 justify-center">
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="font-display font-bold text-slate-100">PROMPTUÁRIO</span>
          </div>

          <div className="mb-8">
            <h2 className="text-2xl font-bold font-display text-slate-100">Entrar</h2>
            <p className="text-slate-500 text-sm mt-1">Acesse sua conta do sistema EHR</p>
          </div>

          {error && (
            <Alert variant="error" className="mb-6">
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            <Input
              label="Email"
              type="email"
              placeholder="seu@email.com"
              icon={<Mail className="w-4 h-4" />}
              error={errors.email?.message}
              {...register('email')}
            />

            <Input
              label="Senha"
              type={showPassword ? 'text' : 'password'}
              placeholder="••••••••"
              icon={<Lock className="w-4 h-4" />}
              error={errors.password?.message}
              suffix={
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="focus:outline-none"
                >
                  {showPassword
                    ? <EyeOff className="w-4 h-4" />
                    : <Eye className="w-4 h-4" />}
                </button>
              }
              {...register('password')}
            />

            <Button
              type="submit"
              className="w-full mt-2"
              size="lg"
              loading={isLoading}
              icon={<ArrowRight className="w-4 h-4" />}
            >
              {isLoading ? 'Entrando…' : 'Entrar'}
            </Button>
          </form>

          {/* Role hints */}
          <div className="mt-8 p-4 bg-slate-900/60 rounded-xl border border-slate-800/60">
            <p className="text-xs font-medium text-slate-500 mb-2">Credenciais padrão</p>
            <div className="space-y-1.5">
              {[
                { role: 'Admin', email: 'admin@promptuario.health', pwd: 'Admin@12345' },
              ].map((c) => (
                <div key={c.role} className="text-xs text-slate-600">
                  <span className="text-brand-400 font-medium">{c.role}:</span>{' '}
                  {c.email} / {c.pwd}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
