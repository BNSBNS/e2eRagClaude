'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'

interface User {
  id: string
  username: string
  email: string
  role: 'admin' | 'standard'
  permissions: string[]
}

interface SessionContextType {
  user: User | null
  token: string | null
  login: (credentials: LoginCredentials) => Promise<void>
  logout: () => void
  isLoading: boolean
  isAuthenticated: boolean
}

interface LoginCredentials {
  username: string
  password: string
}

const SessionContext = createContext<SessionContextType | undefined>(undefined)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const router = useRouter()

  // Initialize session from localStorage on mount
  useEffect(() => {
    const initializeSession = async () => {
      try {
        const storedToken = localStorage.getItem('auth_token')
        const storedUser = localStorage.getItem('user_data')
        
        if (storedToken && storedUser) {
          setToken(storedToken)
          setUser(JSON.parse(storedUser))
          
          // Validate token with backend
          const isValid = await validateToken(storedToken)
          if (!isValid) {
            logout()
          }
        }
      } catch (error) {
        console.error('Session initialization error:', error)
        logout()
      } finally {
        setIsLoading(false)
      }
    }

    initializeSession()
  }, [])

  const login = async (credentials: LoginCredentials) => {
    try {
      setIsLoading(true)
      
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          username: credentials.username,
          password: credentials.password,
        }),
      })

      if (!response.ok) {
        throw new Error('Authentication failed')
      }

      const data = await response.json()
      const { access_token, user_data } = data

      // Store in state
      setToken(access_token)
      setUser(user_data)

      // Persist to localStorage
      localStorage.setItem('auth_token', access_token)
      localStorage.setItem('user_data', JSON.stringify(user_data))

      // Redirect to dashboard
      router.push('/dashboard')
    } catch (error) {
      console.error('Login error:', error)
      throw error
    } finally {
      setIsLoading(false)
    }
  }

  const logout = () => {
    setUser(null)
    setToken(null)
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user_data')
    router.push('/login')
  }

  const validateToken = async (token: string): Promise<boolean> => {
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/validate`, {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      return response.ok
    } catch {
      return false
    }
  }

  const contextValue: SessionContextType = {
    user,
    token,
    login,
    logout,
    isLoading,
    isAuthenticated: !!user && !!token,
  }

  return (
    <SessionContext.Provider value={contextValue}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const context = useContext(SessionContext)
  if (context === undefined) {
    throw new Error('useSession must be used within a SessionProvider')
  }
  return context
}