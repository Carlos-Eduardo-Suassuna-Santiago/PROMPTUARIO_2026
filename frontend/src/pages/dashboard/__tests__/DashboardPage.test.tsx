import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { DashboardPage } from '../DashboardPage'
import { useAuthStore } from '@/store/auth.store'

global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

vi.mock('@/store/auth.store', () => ({
  useAuthStore: vi.fn(),
  useIsDoctor: () => false,
  useIsAdmin: () => false,
  useIsPatient: () => true,
}))

vi.mock('@/hooks', () => ({
  useDashboardSummary: () => ({ data: null, isLoading: false }),
  useAppointments: () => ({ data: { items: [], total: 0 }, isLoading: false }),
  usePatients: () => ({ data: { items: [], total: 0 }, isLoading: false })
}))

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders without crashing', () => {
    ;(useAuthStore as any).mockReturnValue({
      user: { role: 'PATIENT', full_name: 'John Doe' },
    })

    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    )
    expect(container).toBeTruthy()
  })
})
