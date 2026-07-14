import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'

import { Modal } from '@/components/ui/modal'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Alert } from '@/components/ui/alert'
import { recordsApi } from '@/api/services'
import { getErrorMessage } from '@/lib/utils'

const certificateSchema = z.object({
  reason: z.string().min(5, 'O motivo deve ter pelo menos 5 caracteres'),
  days_off: z.coerce.number().min(1, 'A quantidade de dias deve ser pelo menos 1').max(365, 'Máximo de 365 dias'),
  start_date: z.string().min(1, 'A data inicial é obrigatória'),
  notes: z.string().optional(),
})

type CertificateForm = z.infer<typeof certificateSchema>

interface CertificateModalProps {
  recordId: string
  patientId: string
  open: boolean
  onClose: () => void
}

export function CertificateModal({ recordId, patientId, open, onClose }: CertificateModalProps) {
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()

  const createCertificate = useMutation({
    mutationFn: (data: CertificateForm) => recordsApi.createCertificate(recordId, data),
    onSuccess: () => {
      // Invalidate the patient records query to fetch the updated certificates
      qc.invalidateQueries({ queryKey: ['records', 'patient', patientId] })
    },
  })

  const { register, handleSubmit, reset, formState: { errors } } = useForm<CertificateForm>({
    resolver: zodResolver(certificateSchema),
    defaultValues: {
      days_off: 1,
      start_date: new Date().toISOString().split('T')[0],
    },
  })

  const onSubmit = async (data: CertificateForm) => {
    setError(null)
    try {
      await createCertificate.mutateAsync(data)
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Novo Atestado Médico" size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={createCertificate.isPending}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={createCertificate.isPending}>Gerar Atestado</Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Input
            label="Dias de Repouso *"
            type="number"
            min={1}
            max={365}
            error={errors.days_off?.message}
            {...register('days_off')}
          />
          <Input
            label="Data de Início *"
            type="date"
            error={errors.start_date?.message}
            {...register('start_date')}
          />
        </div>

        <Textarea
          label="Motivo / CID *"
          placeholder="Ex: J00 - Nasofaringite aguda"
          rows={2}
          error={errors.reason?.message}
          {...register('reason')}
        />

        <Textarea
          label="Observações (opcional)"
          placeholder="Recomendações adicionais..."
          rows={3}
          error={errors.notes?.message}
          {...register('notes')}
        />
      </div>
    </Modal>
  )
}
