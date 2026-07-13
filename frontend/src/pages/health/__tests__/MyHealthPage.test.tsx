import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { MyHealthPage } from '../MyHealthPage'

// Mock the hooks
vi.mock('@/hooks', () => ({
  useMyPatient: () => ({
    data: { id: 'patient-123', full_name: 'Test Patient' },
    isLoading: false,
  }),
  usePatientAllergies: () => ({
    data: [
      { id: 'allg-1', substance: 'Amendoim', severity: 'SEVERE' }
    ],
    isLoading: false,
  }),
  usePatientVaccines: () => ({
    data: [
      { id: 'vac-1', name: 'Covid-19', dose: '1ª Dose', applied_at: '2023-01-01' }
    ],
    isLoading: false,
  }),
  usePatientMedications: () => ({
    data: [
      { id: 'med-1', name: 'Losartana', dosage: '50mg', frequency: '1x ao dia' }
    ],
    isLoading: false,
  }),
  useAddAllergy: () => ({ mutateAsync: vi.fn() }),
  useDeleteAllergy: () => ({ mutateAsync: vi.fn() })
}))

vi.mock('@/store/auth.store', () => ({
  useIsPatient: () => true
}))

describe('MyHealthPage', () => {
  it('renders the patient health information correctly', () => {
    render(
      <MemoryRouter>
        <MyHealthPage />
      </MemoryRouter>
    )

    // Check titles
    expect(screen.getByText('Minha Saúde')).toBeInTheDocument()
    
    // Check allergy
    expect(screen.getByText('Amendoim')).toBeInTheDocument()
    
    // Check vaccine
    expect(screen.getByText('Covid-19')).toBeInTheDocument()
    
    // Check medication
    expect(screen.getByText('Losartana')).toBeInTheDocument()
    expect(screen.getByText('50mg')).toBeInTheDocument()
  })
})
