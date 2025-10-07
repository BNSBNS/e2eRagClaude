// src/hooks/useAuth.ts - FIXED VERSION
'use client'

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { apiClient } from '@/lib/api';

interface User {
  id: string;
  email: string;
  role: string;
}

export const useAuth = () => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const login = async (username: string, password: string) => {
    try {
      const response = await apiClient.post('/api/auth/login', 
        new URLSearchParams({ username: username, password }).toString(),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
      );
      
      const { access_token } = response.data;
      
      localStorage.setItem('access_token', access_token);
      
      // Fetch user data
      const userResponse = await apiClient.get('/api/auth/me');
      setUser(userResponse.data);
      
      router.push('/dashboard');
    } catch (error) {
      console.error('Login failed:', error);
      throw new Error('Login failed');
    }
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    setUser(null);
    router.push('/login');
  };

  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const response = await apiClient.get('/api/auth/me');
          setUser(response.data);
        } catch (error) {
          console.error('Auth check failed:', error);
          localStorage.removeItem('access_token');
        }
      }
      setLoading(false);
    };

    checkAuth();
  }, []);

  return { 
    user, 
    login, 
    logout, 
    loading,
    isLoading: loading,  
    isAuthenticated: !!user,
  };
};

export const useRequireAuth = () => {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!auth.isLoading && !auth.isAuthenticated) {
      router.push('/login');
    }
  }, [auth.isLoading, auth.isAuthenticated, router]);

  return auth;
};

export const useOptionalAuth = () => {
  return useAuth();
};

export default useAuth;