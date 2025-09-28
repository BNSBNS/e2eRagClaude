'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api'
import { useSession } from '@/app/providers/SessionProvider'

export function useDocuments() {
  const { isAuthenticated } = useSession()
  
  return useQuery({
    queryKey: ['documents'],
    queryFn: () => apiClient.getDocuments(),
    enabled: isAuthenticated,
    staleTime: 1000 * 60 * 5, // 5 minutes
  })
}

export function useUploadDocument() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: ({ file, documentType }: { file: File; documentType: string }) =>
      apiClient.uploadDocument(file, documentType),
    onSuccess: () => {
      // Invalidate and refetch documents list
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
    onError: (error) => {
      console.error('Upload failed:', error)
    },
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: (documentId: string) => apiClient.deleteDocument(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function useDocumentQuery() {
  return useMutation({
    mutationFn: ({ 
      documentId, 
      query, 
      method 
    }: { 
      documentId: string; 
      query: string; 
      method: 'rag' | 'graph' 
    }) => apiClient.queryDocument(documentId, query, method),
  })
}