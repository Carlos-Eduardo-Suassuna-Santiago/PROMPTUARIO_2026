import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, KeyRound, Mail } from 'lucide-react'
import { authApi } from '@/api/services'
import { Button, Input, Alert } from '@/components/ui'
import { getErrorMessage } from '@/utils'

const schema = z.object({
  email: z.string().email('Email inválido'),
})

type FormValues = z.infer<typeof schema>

export function ForgotPasswordPage() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
  })

  const onSubmit = async (data: FormValues) => {
    setStatus('idle')
    setMessage(null)
    try {
      await authApi.requestPasswordReset(data.email)
      setStatus('success')
      setMessage('Se este e-mail estiver cadastrado, enviaremos instruções de recuperação em breve.')
    } catch (err) {
      setStatus('error')
      setMessage(getErrorMessage(err))
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <button
          onClick={() => navigate('/login')}
          className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-slate-200 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Voltar ao login
        </button>

        <div className="mt-6 rounded-2xl border border-slate-800/80 bg-slate-900/60 p-6 shadow-card">
          <div className="w-12 h-12 rounded-2xl bg-brand-500/15 flex items-center justify-center mb-4">
            <KeyRound className="w-6 h-6 text-brand-400" />
          </div>
          <h1 className="text-2xl font-semibold text-slate-100">Recuperar senha</h1>
          <p className="mt-2 text-sm text-slate-500">
            Informe o e-mail associado à sua conta para receber as instruções de recuperação.
          </p>

          {status === 'success' && (
            <Alert variant="success" className="mt-4">
              {message}
            </Alert>
          )}
          {status === 'error' && (
            <Alert variant="error" className="mt-4">
              {message}
            </Alert>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="mt-6 space-y-4">
            <Input
              label="E-mail"
              type="email"
              placeholder="seu@email.com"
              icon={<Mail className="w-4 h-4" />}
              error={errors.email?.message}
              {...register('email')}
            />
            <Button type="submit" className="w-full">
              Enviar instruções
            </Button>
          </form>

          <p className="mt-4 text-xs text-slate-500">
            Se o fluxo de recuperação ainda não estiver habilitado no backend, a interface ficará pronta para integração assim que o endpoint estiver disponível.
          </p>
        </div>
      </div>
    </div>
  )
}
