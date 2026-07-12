import { useState, useEffect } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  UserRound, Save, Lock, MapPin, Phone, Heart, Droplets,
  AlertTriangle, Stethoscope, User,
} from 'lucide-react'
import { useUpdateUser, useMyPatient, useUpdatePatient } from '@/hooks'
import { useAuthStore, useIsPatient } from '@/store/auth.store'
import { authApi } from '@/api/services'
import { PageHeader } from '@/components/layout/AppShell'
import {
  Card, CardHeader, CardBody, Button, Input, Alert, PageLoader, Select, Textarea,
} from '@/components/ui'
import { ROLE_LABELS, formatDate, initials, getErrorMessage } from '@/utils'

const profileSchema = z.object({
  full_name: z.string().min(2, 'Nome deve ter no mínimo 2 caracteres'),
  email: z.string().email('Email inválido'),
})
type ProfileForm = z.infer<typeof profileSchema>

const patientSchema = z.object({
  cpf: z.string().optional(),
  date_of_birth: z.string().optional(),
  gender: z.string().optional(),
  blood_type: z.string().optional(),
  phone: z.string().optional(),
  street: z.string().optional(),
  city: z.string().optional(),
  state: z.string().optional(),
  zip_code: z.string().optional(),
  emergency_name: z.string().optional(),
  emergency_phone: z.string().optional(),
  emergency_relation: z.string().optional(),
  notes: z.string().optional(),
})
type PatientForm = z.infer<typeof patientSchema>

const passwordSchema = z.object({
  current_password: z.string().min(1, 'Senha atual obrigatória'),
  new_password: z.string().min(6, 'Nova senha deve ter no mínimo 6 caracteres'),
  confirm_password: z.string().min(1, 'Confirmação de senha obrigatória'),
}).refine((data) => data.new_password === data.confirm_password, {
  message: 'Senhas não conferem',
  path: ['confirm_password'],
})
type PasswordForm = z.infer<typeof passwordSchema>

export function ProfilePage() {
  const { user } = useAuthStore()
  const isPatient = useIsPatient()
  const updateUser = useUpdateUser()
  const updatePatient = useUpdatePatient()
  const { data: patient, isLoading: patientLoading } = useMyPatient()

  const [profileError, setProfileError] = useState<string | null>(null)
  const [profileSuccess, setProfileSuccess] = useState(false)
  const [patientError, setPatientError] = useState<string | null>(null)
  const [patientSuccess, setPatientSuccess] = useState(false)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordSuccess, setPasswordSuccess] = useState(false)

  const {
    register: registerProfile,
    handleSubmit: handleSubmitProfile,
    formState: { errors: profileErrors, isDirty: profileDirty },
  } = useForm<ProfileForm>({
    resolver: zodResolver(profileSchema),
    values: {
      full_name: user?.full_name ?? '',
      email: user?.email ?? '',
    },
  })

  const {
    register: registerPatient,
    handleSubmit: handleSubmitPatient,
    reset: resetPatient,
    formState: { errors: patientErrors, isDirty: patientDirty },
  } = useForm<PatientForm>({
    resolver: zodResolver(patientSchema),
    values: {
      cpf: patient?.cpf ?? '',
      date_of_birth: patient?.date_of_birth ?? '',
      gender: patient?.gender ?? '',
      blood_type: patient?.blood_type ?? '',
      phone: patient?.phone ?? '',
      street: patient?.street ?? '',
      city: patient?.city ?? '',
      state: patient?.state ?? '',
      zip_code: patient?.zip_code ?? '',
      emergency_name: patient?.emergency_name ?? '',
      emergency_phone: patient?.emergency_phone ?? '',
      emergency_relation: patient?.emergency_relation ?? '',
      notes: patient?.notes ?? '',
    },
  })

  const {
    register: registerPassword,
    handleSubmit: handleSubmitPassword,
    reset: resetPassword,
    formState: { errors: passwordErrors },
  } = useForm<PasswordForm>({
    resolver: zodResolver(passwordSchema),
  })

  const onProfileSubmit = async (data: ProfileForm) => {
    setProfileError(null)
    setProfileSuccess(false)
    if (!user) return
    try {
      await updateUser.mutateAsync({ id: user.id, data })
      setProfileSuccess(true)
      setTimeout(() => setProfileSuccess(false), 3000)
    } catch (err) {
      setProfileError(getErrorMessage(err))
    }
  }

  const onPatientSubmit = async (data: PatientForm) => {
    setPatientError(null)
    setPatientSuccess(false)
    if (!patient) return
    try {
      await updatePatient.mutateAsync({
        id: patient.id,
        data: {
          cpf: data.cpf || undefined,
          date_of_birth: data.date_of_birth || undefined,
          gender: (data.gender as 'M' | 'F' | 'OTHER') || undefined,
          blood_type: data.blood_type || undefined,
          phone: data.phone ?? undefined,
          address: {
            street: data.street ?? undefined,
            city: data.city ?? undefined,
            state: data.state ?? undefined,
            zip_code: data.zip_code ?? undefined,
          },
          emergency_contact: {
            name: data.emergency_name ?? undefined,
            phone: data.emergency_phone ?? undefined,
            relation: data.emergency_relation ?? undefined,
          },
          notes: data.notes ?? undefined,
        },
      })
      setPatientSuccess(true)
      setTimeout(() => setPatientSuccess(false), 3000)
    } catch (err) {
      setPatientError(getErrorMessage(err))
    }
  }

  const onPasswordSubmit = async (data: PasswordForm) => {
    setPasswordError(null)
    setPasswordSuccess(false)
    try {
      await authApi.changePassword(data.current_password, data.new_password)
      setPasswordSuccess(true)
      resetPassword()
      setTimeout(() => setPasswordSuccess(false), 3000)
    } catch (err) {
      setPasswordError(getErrorMessage(err))
    }
  }

  if (!user) return <PageLoader />

  return (
    <div>
      <PageHeader
        title="Meu Perfil"
        description="Gerencie suas informações pessoais e de paciente"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Profile info card */}
        <div className="lg:col-span-1">
          <Card>
            <CardBody className="flex flex-col items-center text-center py-8">
              <div className="w-20 h-20 rounded-full bg-brand-500/20 border border-brand-500/30 flex items-center justify-center mb-4">
                <span className="text-2xl font-bold text-brand-300">
                  {initials(user.full_name)}
                </span>
              </div>
              <h2 className="text-lg font-semibold text-slate-200">{user.full_name}</h2>
              <p className="text-sm text-slate-500 mt-1">{user.email}</p>
              <span className="mt-3 px-3 py-1 rounded-full text-xs font-medium bg-brand-500/15 text-brand-300 ring-1 ring-brand-500/20">
                {ROLE_LABELS[user.role]}
              </span>
              <div className="mt-6 w-full space-y-2 text-left">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Membro desde</span>
                  <span className="text-slate-300">{formatDate(user.created_at)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-slate-500">Status</span>
                  <span className={user.is_active ? 'text-emerald-400' : 'text-rose-400'}>
                    {user.is_active ? 'Ativo' : 'Inativo'}
                  </span>
                </div>
                {patient && (
                  <>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">CPF</span>
                      <span className="text-slate-300">{patient.cpf || '—'}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">Tipo Sanguíneo</span>
                      <span className="text-slate-300">{patient.blood_type || '—'}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-slate-500">Telefone</span>
                      <span className="text-slate-300">{patient.phone || '—'}</span>
                    </div>
                  </>
                )}
              </div>
            </CardBody>
          </Card>
        </div>

        {/* Edit forms */}
        <div className="lg:col-span-2 space-y-6">
          {/* User info card */}
          <Card>
            <CardHeader>
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <UserRound className="w-4 h-4 text-brand-400" />
                Informações da Conta
              </h3>
            </CardHeader>
            <CardBody>
              {profileSuccess && (
                <Alert variant="success" className="mb-5">Perfil atualizado com sucesso!</Alert>
              )}
              {profileError && (
                <Alert variant="error" className="mb-5">{profileError}</Alert>
              )}
              <form onSubmit={handleSubmitProfile(onProfileSubmit)} className="space-y-5">
                <Input
                  label="Nome completo"
                  placeholder="Seu nome"
                  error={profileErrors.full_name?.message}
                  {...registerProfile('full_name')}
                />
                <Input
                  label="Email"
                  type="email"
                  placeholder="seu@email.com"
                  error={profileErrors.email?.message}
                  {...registerProfile('email')}
                />
                <div className="flex justify-end pt-2">
                  <Button
                    type="submit"
                    icon={<Save className="w-4 h-4" />}
                    loading={updateUser.isPending}
                    disabled={!profileDirty}
                  >
                    Salvar Alterações
                  </Button>
                </div>
              </form>
            </CardBody>
          </Card>

          {/* Patient info card — only for patients */}
          {isPatient && (
            <Card>
              <CardHeader>
                <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                  <User className="w-4 h-4 text-brand-400" />
                  Dados do Paciente
                </h3>
              </CardHeader>
              <CardBody>
                {patientLoading ? (
                  <PageLoader />
                ) : (
                  <>
                    {patientSuccess && (
                      <Alert variant="success" className="mb-5">Dados atualizados com sucesso!</Alert>
                    )}
                    {patientError && (
                      <Alert variant="error" className="mb-5">{patientError}</Alert>
                    )}
                    <form onSubmit={handleSubmitPatient(onPatientSubmit)} className="space-y-5">
                      {/* Personal data */}
                      <div>
                        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <User className="w-3.5 h-3.5" /> Dados Pessoais
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <Input
                            label="CPF"
                            placeholder="000.000.000-00"
                            error={patientErrors.cpf?.message}
                            disabled={!!patient?.cpf}
                            {...registerPatient('cpf')}
                          />
                          <Input
                            label="Data de Nascimento"
                            type="date"
                            error={patientErrors.date_of_birth?.message}
                            disabled={!!patient?.date_of_birth}
                            {...registerPatient('date_of_birth')}
                          />
                          <Select
                            label="Gênero"
                            placeholder="Selecione"
                            options={[
                              { value: 'M', label: 'Masculino' },
                              { value: 'F', label: 'Feminino' },
                              { value: 'OTHER', label: 'Outro' },
                            ]}
                            error={patientErrors.gender?.message}
                            disabled={!!patient?.gender}
                            {...registerPatient('gender')}
                          />
                          <Select
                            label="Tipo Sanguíneo"
                            placeholder="Selecione"
                            options={[
                              { value: 'A+', label: 'A+' },
                              { value: 'A-', label: 'A-' },
                              { value: 'B+', label: 'B+' },
                              { value: 'B-', label: 'B-' },
                              { value: 'AB+', label: 'AB+' },
                              { value: 'AB-', label: 'AB-' },
                              { value: 'O+', label: 'O+' },
                              { value: 'O-', label: 'O-' },
                            ]}
                            error={patientErrors.blood_type?.message}
                            disabled={!!patient?.blood_type}
                            {...registerPatient('blood_type')}
                          />
                          <Input
                            label="Telefone"
                            placeholder="(11) 99999-9999"
                            icon={<Phone className="w-4 h-4" />}
                            error={patientErrors.phone?.message}
                            {...registerPatient('phone')}
                          />
                        </div>
                      </div>

                      {/* Address */}
                      <div className="pt-4 border-t border-slate-800/60">
                        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <MapPin className="w-3.5 h-3.5" /> Endereço
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div className="md:col-span-2">
                            <Input
                              label="Logradouro"
                              placeholder="Rua, número, bairro"
                              error={patientErrors.street?.message}
                              {...registerPatient('street')}
                            />
                          </div>
                          <Input
                            label="Cidade"
                            placeholder="Sua cidade"
                            error={patientErrors.city?.message}
                            {...registerPatient('city')}
                          />
                          <Input
                            label="Estado"
                            placeholder="SP"
                            maxLength={2}
                            error={patientErrors.state?.message}
                            {...registerPatient('state')}
                          />
                          <Input
                            label="CEP"
                            placeholder="00000-000"
                            error={patientErrors.zip_code?.message}
                            {...registerPatient('zip_code')}
                          />
                        </div>
                      </div>

                      {/* Emergency contact */}
                      <div className="pt-4 border-t border-slate-800/60">
                        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <AlertTriangle className="w-3.5 h-3.5" /> Contato de Emergência
                        </h4>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <Input
                            label="Nome do Contato"
                            placeholder="Nome completo"
                            icon={<UserRound className="w-4 h-4" />}
                            error={patientErrors.emergency_name?.message}
                            {...registerPatient('emergency_name')}
                          />
                          <Input
                            label="Telefone do Contato"
                            placeholder="(11) 99999-9999"
                            icon={<Phone className="w-4 h-4" />}
                            error={patientErrors.emergency_phone?.message}
                            {...registerPatient('emergency_phone')}
                          />
                          <Input
                            label="Parentesco / Relação"
                            placeholder="Cônjuge, filho(a), etc."
                            error={patientErrors.emergency_relation?.message}
                            {...registerPatient('emergency_relation')}
                          />
                        </div>
                      </div>

                      {/* Notes */}
                      <div className="pt-4 border-t border-slate-800/60">
                        <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                          <Heart className="w-3.5 h-3.5" /> Observações
                        </h4>
                        <Textarea
                          label="Observações gerais"
                          placeholder="Alergias, condições preexistentes, informações relevantes..."
                          rows={3}
                          error={patientErrors.notes?.message}
                          {...registerPatient('notes')}
                        />
                      </div>

                      <div className="flex justify-end pt-2">
                        <Button
                          type="submit"
                          icon={<Save className="w-4 h-4" />}
                          loading={updatePatient.isPending}
                          disabled={!patientDirty}
                        >
                          Salvar Dados do Paciente
                        </Button>
                      </div>
                    </form>
                  </>
                )}
              </CardBody>
            </Card>
          )}

          {/* Change password card */}
          <Card>
            <CardHeader>
              <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                <Lock className="w-4 h-4 text-brand-400" />
                Alterar Senha
              </h3>
            </CardHeader>
            <CardBody>
              {passwordSuccess && (
                <Alert variant="success" className="mb-5">Senha alterada com sucesso!</Alert>
              )}
              {passwordError && (
                <Alert variant="error" className="mb-5">{passwordError}</Alert>
              )}
              <form onSubmit={handleSubmitPassword(onPasswordSubmit)} className="space-y-5">
                <Input
                  label="Senha atual"
                  type="password"
                  placeholder="••••••"
                  error={passwordErrors.current_password?.message}
                  {...registerPassword('current_password')}
                />
                <Input
                  label="Nova senha"
                  type="password"
                  placeholder="Mínimo 6 caracteres"
                  error={passwordErrors.new_password?.message}
                  {...registerPassword('new_password')}
                />
                <Input
                  label="Confirmar nova senha"
                  type="password"
                  placeholder="Repita a nova senha"
                  error={passwordErrors.confirm_password?.message}
                  {...registerPassword('confirm_password')}
                />
                <div className="flex justify-end pt-2">
                  <Button type="submit" icon={<Lock className="w-4 h-4" />}>
                    Alterar Senha
                  </Button>
                </div>
              </form>
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  )
}