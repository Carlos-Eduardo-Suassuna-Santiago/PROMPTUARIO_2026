import { useEffect, useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, ShieldCheck, KeyRound } from 'lucide-react'
import { authApi } from '@/api/services'
import { Button, Input, Alert } from '@/components/ui'
import { getErrorMessage } from '@/utils'

const schema = z.object({
  code: z.string().min(4, 'Informe o código de verificação'),
})

type FormValues = z.infer<typeof schema>

export function TwoFactorPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState<string | null>(null)
  const [email, setEmail] = useState<string>('')

  useEffect(() => {
    const state = location.state as { email?: string } | null
    if (state?.email) {
      setEmail(state.email)
    }
  }, [location.state])

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
      await authApi.verifyTwoFactor(email, data.code)
      setStatus('success')
      setMessage('Código validado com sucesso. Você já pode continuar para o painel.')
      setTimeout(() => navigate('/dashboard', { replace: true }), 900)
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
            <ShieldCheck className="w-6 h-6 text-brand-400" />
          </div>
          <h1 className="text-2xl font-semibold text-slate-100">Verificação em duas etapas</h1>
          <p className="mt-2 text-sm text-slate-500">
            Digite o código recebido para concluir a autenticação.
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
              label="Código de verificação"
              placeholder="123456"
              icon={<KeyRound className="w-4 h-4" />}
              error={errors.code?.message}
              {...register('code')}
            />
            <Button type="submit" className="w-full">
              Confirmar código
            </Button>
          </form>

          <p className="mt-4 text-xs text-slate-500">
            {email ? `A validação está preparada para ${email}.` : 'O fluxo pode ser usado após o backend expedir o desafio de 2FA.'}
          </p>
        </div>
      </div>
    </div>
  )
}
