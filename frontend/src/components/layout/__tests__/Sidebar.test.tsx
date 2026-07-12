import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from '../Sidebar'
import { useAuthStore } from '@/store/auth.store'

vi.mock('@/store/auth.store', () => ({
  useAuthStore: vi.fn(),
  useRole: () => 'PATIENT',
}))

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders without crashing', () => {
    ;(useAuthStore as any).mockReturnValue({
      user: { full_name: 'John Patient' },
      logout: vi.fn()
    })

    const { container } = render(
      <MemoryRouter>
        <Sidebar mobileOpen={false} setMobileOpen={vi.fn()} />
      </MemoryRouter>
    )
    expect(container).toBeTruthy()
  })
})
