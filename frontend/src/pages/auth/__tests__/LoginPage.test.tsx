import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { LoginPage } from '../LoginPage'
import { useLogin } from '@/hooks'

vi.mock('@/hooks', () => ({
  useLogin: vi.fn(),
}))

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(useLogin as any).mockReturnValue({
      mutateAsync: vi.fn(),
      isPending: false,
    })
  })

  it('renders without crashing', () => {
    const { container } = render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    )
    expect(container).toBeTruthy()
  })
})
