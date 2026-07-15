import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Activity, Mail, ArrowLeft, ArrowRight, CheckCircle } from 'lucide-react'
import { Button, Input, Alert } from '@/components/ui'
import { authApi } from '@/api/services'
import { getErrorMessage } from '@/utils'

const schema = z.object({
  email: z.string().email('Email inválido'),
})

type FormValues = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)
  const [resetToken, setResetToken] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormValues) => {
    setError(null)
    setIsLoading(true)
    try {
      const resp = await authApi.forgotPassword(data.email)
      if (resp.reset_token) setResetToken(resp.reset_token)
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
          <h2 className="text-2xl font-bold font-display text-slate-100 mb-2">Email enviado!</h2>
          <p className="text-slate-400 text-sm mb-8">
            Se o email estiver cadastrado, você receberá um link para redefinir sua senha.
          </p>
          {resetToken && (
            <Button
              className="w-full mb-3 bg-brand-500 hover:bg-brand-600 text-white"
              onClick={() => navigate(`/reset-password?token=${resetToken}`)}
            >
              Simular Link do E-mail
            </Button>
          )}
          <Button
            variant="outline"
            className="w-full"
            onClick={() => navigate('/login')}
            icon={<ArrowLeft className="w-4 h-4" />}
          >
            Voltar ao login
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-950 flex">
      {/* Left panel — decorative */}
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
              Esqueceu
              <br />
              <span className="text-brand-400">sua senha?</span>
            </h1>
            <p className="text-slate-400 text-lg leading-relaxed max-w-sm">
              Informe seu email cadastrado e enviaremos as instruções para redefinir sua senha.
            </p>
          </div>
          <p className="text-xs text-slate-600">© 2026 PROMPTUÁRIO · Versão 1.0.0</p>
        </div>
      </div>

      {/* Right panel — form */}
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
            <h2 className="text-2xl font-bold font-display text-slate-100">Redefinir senha</h2>
            <p className="text-slate-500 text-sm mt-1">
              Digite seu email para receber as instruções
            </p>
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

            <Button
              type="submit"
              className="w-full mt-2"
              size="lg"
              loading={isLoading}
              icon={<ArrowRight className="w-4 h-4" />}
            >
              {isLoading ? 'Enviando…' : 'Enviar instruções'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <Link
              to="/login"
              className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
            >
              Lembrou sua senha? <span className="text-brand-400">Entrar</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}