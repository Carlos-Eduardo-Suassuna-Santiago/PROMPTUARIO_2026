import { useState } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Activity, Lock, Eye, EyeOff, ArrowLeft, CheckCircle } from 'lucide-react'
import { Button, Input, Alert } from '@/components/ui'
import { authApi } from '@/api/services'
import { getErrorMessage } from '@/utils'

const schema = z.object({
  new_password: z
    .string()
    .min(8, 'Mínimo 8 caracteres')
    .regex(/[A-Z]/, 'Deve conter ao menos uma letra maiúscula')
    .regex(/[0-9]/, 'Deve conter ao menos um número'),
  confirm_password: z.string(),
}).refine((data) => data.new_password === data.confirm_password, {
  message: 'Senhas não conferem',
  path: ['confirm_password'],
})

type FormValues = z.infer<typeof schema>

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormValues) => {
    if (!token) {
      setError('Token de redefinição não encontrado.')
      return
    }
    setError(null)
    setIsLoading(true)
    try {
      await authApi.resetPassword(token, data.new_password)
      setSuccess(true)
    } catch (err) {
      setError(getErrorMessage(err))
    } finally {
      setIsLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
        <div className="w-full max-w-sm text-center animate-slide-up">
          <div className="w-16 h-16 rounded-2xl bg-emerald-500/15 flex items-center justify-center mx-auto mb-6">
            <CheckCircle className="w-8 h-8 text-emerald-400" />
          </div>
          <h2 className="text-2xl font-bold font-display text-slate-100 mb-2">Senha redefinida!</h2>
          <p className="text-slate-400 text-sm mb-8">
            Sua senha foi alterada com sucesso. Agora você pode entrar com sua nova senha.
          </p>
          <Button
            className="w-full"
            onClick={() => navigate('/login')}
          >
            Ir para o login
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 flex">
      {/* Left panel */}
      <div className="hidden lg:flex w-1/2 relative overflow-hidden bg-slate-900">
        <div className="absolute inset-0 bg-grid-pattern bg-grid opacity-40" />
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-brand-500/10 rounded-full blur-3xl" />
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-brand-500 flex items-center justify-center shadow-glow-brand">
              <Activity className="w-5 h-5 text-white" />
            </div>
            <span className="font-display font-bold text-xl text-slate-100">PROMPTUÁRIO</span>
          </div>
          <div>
            <h1 className="text-5xl font-bold font-display text-slate-100 leading-tight mb-4">
              Redefinir
              <br />
              <span className="text-brand-400">sua senha</span>
            </h1>
            <p className="text-slate-400 text-lg leading-relaxed max-w-sm">
              Escolha uma nova senha forte para proteger sua conta.
            </p>
          </div>
          <p className="text-xs text-slate-600">© 2026 PROMPTUÁRIO · Versão 1.0.0</p>
        </div>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm animate-slide-up">
          <div className="flex lg:hidden items-center gap-2 mb-10 justify-center">
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
              <Activity className="w-4 h-4 text-white" />
            </div>
            <span className="font-display font-bold text-slate-100">PROMPTUÁRIO</span>
          </div>

          <div className="mb-8">
            <button
              onClick={() => navigate('/login')}
              className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 mb-4 transition-colors"
            >
              <ArrowLeft className="w-4 h-4" />
              Voltar
            </button>
            <h2 className="text-2xl font-bold font-display text-slate-100">Nova senha</h2>
            <p className="text-slate-500 text-sm mt-1">
              {token ? 'Digite sua nova senha' : 'Link inválido ou expirado'}
            </p>
          </div>

          {error && (
            <Alert variant="error" className="mb-6">
              {error}
            </Alert>
          )}

          {!token ? (
            <div className="text-center">
              <p className="text-slate-400 text-sm mb-4">
                O link para redefinir senha é inválido ou expirou.
              </p>
              <Button
                variant="outline"
                className="w-full"
                onClick={() => navigate('/forgot-password')}
              >
                Solicitar novo link
              </Button>
            </div>
          ) : (
            <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
              <Input
                label="Nova senha"
                type={showPassword ? 'text' : 'password'}
                placeholder="••••••••"
                icon={<Lock className="w-4 h-4" />}
                error={errors.new_password?.message}
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
                {...register('new_password')}
              />

              <Input
                label="Confirmar senha"
                type={showConfirm ? 'text' : 'password'}
                placeholder="••••••••"
                icon={<Lock className="w-4 h-4" />}
                error={errors.confirm_password?.message}
                suffix={
                  <button
                    type="button"
                    onClick={() => setShowConfirm((v) => !v)}
                    className="focus:outline-none"
                  >
                    {showConfirm
                      ? <EyeOff className="w-4 h-4" />
                      : <Eye className="w-4 h-4" />}
                  </button>
                }
                {...register('confirm_password')}
              />

              <Button
                type="submit"
                className="w-full mt-2"
                size="lg"
                loading={isLoading}
              >
                {isLoading ? 'Redefinindo…' : 'Redefinir senha'}
              </Button>
            </form>
          )}

          <div className="mt-6 text-center">
            <Link
              to="/login"
              className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
            >
              Voltar ao <span className="text-brand-400">login</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}