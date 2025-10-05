import { renderHook, waitFor } from '@testing-library/react'
import { useAuth } from '@/hooks/useAuth'

describe('useAuth', () => {
  beforeEach(() => {
    localStorage.clear()
    jest.clearAllMocks()
  })

  it('should return loading true initially', () => {
    const { result } = renderHook(() => useAuth())
    expect(result.current.loading).toBe(true)
  })

  it('should return user after successful login', async () => {
    const mockUser = { id: '1', email: 'test@example.com', role: 'user' }
    
    global.fetch = jest.fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ access_token: 'fake-token' })
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser
      })

    const { result } = renderHook(() => useAuth())

    await waitFor(() => {
      expect(result.current.user).toEqual(mockUser)
      expect(result.current.isAuthenticated).toBe(true)
    })
  })
})