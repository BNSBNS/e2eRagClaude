// frontend/src/app/providers/SessionProvider.tsx
'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { useRouter } from 'next/navigation'

interface User {
  id: number
  username: string
  email: string
  role: 'user' | 'admin'
  full_name?: string
  is_active: boolean
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

  // THIS IS KEY - Get API URL from environment
  const API_URL = typeof window !== 'undefined' 
    ? (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000')
    : 'http://fastapi-backend:8000'  // Server-side uses container name

  useEffect(() => {
    initializeSession()
  }, [])

  const initializeSession = async () => {
    try {
      const storedToken = localStorage.getItem('access_token')
      
      if (storedToken) {
        setToken(storedToken)
        const isValid = await fetchUserProfile(storedToken)
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

  const fetchUserProfile = async (authToken: string): Promise<boolean> => {
    try {
      console.log('Fetching user profile from:', `${API_URL}/api/auth/me`)
      
      const response = await fetch(`${API_URL}/api/auth/me`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${authToken}`,
          'Content-Type': 'application/json',
        },
      })

      console.log('Profile response status:', response.status)

      if (!response.ok) {
        console.error('Profile fetch failed')
        return false
      }

      const userData = await response.json()
      console.log('User loaded:', userData.username)
      setUser(userData)
      return true
    } catch (error) {
      console.error('Failed to fetch user profile:', error)
      return false
    }
  }

  const login = async (credentials: LoginCredentials) => {
    try {
      setIsLoading(true)
      
      console.log('Logging in to:', `${API_URL}/api/auth/login`)
      
      const formData = new URLSearchParams()
      formData.append('username', credentials.username)
      formData.append('password', credentials.password)
      
      const response = await fetch(`${API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
          'Accept': 'application/json',
        },
        body: formData,
      })

      console.log('Login response status:', response.status)
      
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || 'Authentication failed')
      }

      const data = await response.json()
      console.log('Login successful')
      
      const { access_token } = data

      setToken(access_token)
      localStorage.setItem('access_token', access_token)

      const profileLoaded = await fetchUserProfile(access_token)
      
      if (profileLoaded) {
        console.log('Redirecting to dashboard...')
        router.push('/dashboard')
      } else {
        throw new Error('Failed to load user profile')
      }
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
    localStorage.removeItem('access_token')
    router.push('/login')
  }

  return (
    <SessionContext.Provider value={{ user, token, login, logout, isLoading, isAuthenticated: !!user && !!token }}>
      {children}
    </SessionContext.Provider>
  )
}

export function useSession() {
  const context = useContext(SessionContext)
  if (!context) {
    throw new Error('useSession must be used within a SessionProvider')
  }
  return context
}