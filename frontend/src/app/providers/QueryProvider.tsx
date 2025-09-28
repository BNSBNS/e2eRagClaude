'use client'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { useState, ReactNode } from 'react'

export function QueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Stale time for AI responses (longer cache for expensive operations)
            staleTime: 1000 * 60 * 5, // 5 minutes
            // Retry logic for AI API calls
            retry: (failureCount, error: any) => {
              // Don't retry on authentication errors
              if (error?.status === 401 || error?.status === 403) {
                return false
              }
              // Retry up to 3 times for other errors
              return failureCount < 3
            },
            // Refetch on window focus for real-time document updates
            refetchOnWindowFocus: true,
            // Network error handling
            retryDelay: attemptIndex => Math.min(1000 * 2 ** attemptIndex, 30000),
          },
          mutations: {
            // Mutation retry logic for file uploads and processing
            retry: (failureCount, error: any) => {
              if (error?.status === 413) { // File too large
                return false
              }
              return failureCount < 2
            },
            // Handle mutation errors globally
            onError: (error: any) => {
              console.error('Mutation error:', error)
              // Could integrate with toast notifications here
            },
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {process.env.NODE_ENV === 'development' && (
        <ReactQueryDevtools initialIsOpen={false} />
      )}
    </QueryClientProvider>
  )
}