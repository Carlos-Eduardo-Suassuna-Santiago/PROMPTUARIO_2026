import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Activity, Mail, Lock, Eye, EyeOff, User, Phone, Calendar, ArrowLeft, ArrowRight, CheckCircle } from 'lucide-react'
import { Button, Input, Alert, Select } from '@/components/ui'
import { authApi } from '@/api/services'
import { getErrorMessage } from '@/utils'

const schema = z.object({
  full_name: z.string().min(2, 'Mínimo 2 caracteres').max(255, 'Máximo 255 caracteres'),
  email: z.string().email('Email inválido'),
  password: z
    .string()
    .min(8, 'Mínimo 8 caracteres')
    .regex(/[A-Z]/, 'Deve conter ao menos uma letra maiúscula')
    .regex(/[0-9]/, 'Deve conter ao menos um número'),
  confirm_password: z.string(),
  cpf: z.string().optional(),
  date_of_birth: z.string().optional(),
  gender: z.string().optional(),
  phone: z.string().optional(),
}).refine((data) => data.password === data.confirm_password, {
  message: 'Senhas não conferem',
  path: ['confirm_password'],
})

type FormValues = z.infer<typeof schema>

export function PatientRegisterPage() {
  const navigate = useNavigate()
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
    setError(null)
    setIsLoading(true)
    try {
      await authApi.registerPatient({
        email: data.email,
        password: data.password,
        full_name: data.full_name,
        cpf: data.cpf || undefined,
        date_of_birth: data.date_of_birth || undefined,
        gender: data.gender || undefined,
        phone: data.phone || undefined,
      })
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
          <h2 className="text-2xl font-bold font-display text-slate-100 mb-2">Cadastro realizado!</h2>
          <p className="text-slate-400 text-sm mb-8">
            Sua conta foi criada com sucesso. Agora você pode acessar o sistema.
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
              Cadastro
              <br />
              <span className="text-brand-400">de Paciente</span>
            </h1>
            <p className="text-slate-400 text-lg leading-relaxed max-w-sm">
              Crie sua conta para acessar o sistema de prontuário eletrônico e agendar consultas.
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
            <h2 className="text-2xl font-bold font-display text-slate-100">Criar conta</h2>
            <p className="text-slate-500 text-sm mt-1">
              Preencha os dados para se cadastrar como paciente
            </p>
          </div>

          {error && (
            <Alert variant="error" className="mb-6">
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label="Nome completo"
              placeholder="Seu nome completo"
              icon={<User className="w-4 h-4" />}
              error={errors.full_name?.message}
              {...register('full_name')}
            />

            <Input
              label="Email"
              type="email"
              placeholder="seu@email.com"
              icon={<Mail className="w-4 h-4" />}
              error={errors.email?.message}
              {...register('email')}
            />

            <div className="grid grid-cols-2 gap-3">
              <Input
                label="CPF"
                placeholder="000.000.000-00"
                error={errors.cpf?.message}
                {...register('cpf')}
              />
              <Input
                label="Data de nasc."
                type="date"
                error={errors.date_of_birth?.message}
                {...register('date_of_birth')}
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Select
                label="Gênero"
                placeholder="Selecione"
                options={[
                  { value: 'M', label: 'Masculino' },
                  { value: 'F', label: 'Feminino' },
                  { value: 'OTHER', label: 'Outro' },
                ]}
                error={errors.gender?.message}
                {...register('gender')}
              />
              <Input
                label="Telefone"
                placeholder="(11) 99999-9999"
                icon={<Phone className="w-4 h-4" />}
                error={errors.phone?.message}
                {...register('phone')}
              />
            </div>

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
              icon={<ArrowRight className="w-4 h-4" />}
            >
              {isLoading ? 'Cadastrando…' : 'Cadastrar'}
            </Button>
          </form>

          <div className="mt-6 text-center">
            <Link
              to="/login"
              className="text-sm text-slate-500 hover:text-slate-300 transition-colors"
            >
              Já tem conta? <span className="text-brand-400">Entrar</span>
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
}