import { useState } from 'react'
import { useForm, useFieldArray } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'

import { Modal, Button, Input, Textarea, Alert } from '@/components/ui'
import { recordsApi } from '@/api/services'
import { getErrorMessage } from '@/utils'

const prescriptionSchema = z.object({
  medications: z.array(z.object({
    name: z.string().min(1),
    dosage: z.string().min(1),
    frequency: z.string().min(1),
    duration_days: z.coerce.number().min(1),
    instructions: z.string().optional(),
  })).min(1, 'Adicione ao menos um medicamento'),
  instructions: z.string().optional(),
  valid_days: z.coerce.number().default(30),
})

type PrescriptionForm = z.infer<typeof prescriptionSchema>

interface PrescriptionModalProps {
  recordId: string
  patientId: string
  open: boolean
  onClose: () => void
}

export function PrescriptionModal({ recordId, patientId, open, onClose }: PrescriptionModalProps) {
  const [error, setError] = useState<string | null>(null)
  const qc = useQueryClient()

  const createPrescription = useMutation({
    mutationFn: (data: { recordId: string; data: PrescriptionForm }) => 
      recordsApi.createPrescription(data.recordId, data.data),
    onSuccess: () => {
      // Invalidate the patient records query to fetch the updated prescriptions
      qc.invalidateQueries({ queryKey: ['records', 'patient', patientId] })
    },
  })

  const { register, handleSubmit, control, reset, formState: { errors } } = useForm<PrescriptionForm>({
    resolver: zodResolver(prescriptionSchema),
    defaultValues: { medications: [{ name: '', dosage: '', frequency: '', duration_days: 7 }], valid_days: 30 },
  })

  const { fields, append, remove } = useFieldArray({ control, name: 'medications' })

  const onSubmit = async (data: PrescriptionForm) => {
    setError(null)
    try {
      await createPrescription.mutateAsync({ recordId, data })
      reset()
      onClose()
    } catch (err) {
      setError(getErrorMessage(err))
    }
  }

  return (
    <Modal open={open} onClose={onClose} title="Nova Prescrição" size="xl"
      footer={
        <>
          <Button variant="ghost" onClick={onClose} disabled={createPrescription.isPending}>Cancelar</Button>
          <Button onClick={handleSubmit(onSubmit)} loading={createPrescription.isPending}>
            Gerar Prescrição
          </Button>
        </>
      }
    >
      {error && <Alert variant="error" className="mb-4">{error}</Alert>}
      <div className="space-y-4">
        {fields.map((field, i) => (
          <div key={field.id} className="p-4 bg-slate-950/60 rounded-xl border border-slate-800/60 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-slate-400">Medicamento {i + 1}</span>
              {i > 0 && (
                <button onClick={() => remove(i)} className="text-xs text-rose-400 hover:underline">
                  Remover
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Input label="Nome *" placeholder="Dipirona" {...register(`medications.${i}.name` as const)} />
              <Input label="Dosagem *" placeholder="500mg" {...register(`medications.${i}.dosage` as const)} />
              <Input label="Frequência *" placeholder="6/6h" {...register(`medications.${i}.frequency` as const)} />
              <Input label="Dias *" type="number" placeholder="7" {...register(`medications.${i}.duration_days` as const)} />
            </div>
            <Input label="Instruções" placeholder="Tomar com água…" {...register(`medications.${i}.instructions` as const)} />
          </div>
        ))}

        <Button
          variant="outline"
          size="sm"
          icon={<Plus className="w-3.5 h-3.5" />}
          onClick={() => append({ name: '', dosage: '', frequency: '', duration_days: 7 })}
        >
          Adicionar medicamento
        </Button>

        <div className="grid grid-cols-2 gap-4 pt-2 border-t border-slate-800">
          <Textarea label="Instruções gerais" rows={2} {...register('instructions')} />
          <Input label="Validade (dias)" type="number" {...register('valid_days')} />
        </div>
      </div>
    </Modal>
  )
}
