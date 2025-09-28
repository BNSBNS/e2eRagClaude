'use client'

import { useRequireAuth } from '@/hooks/useAuth'  // Now this will work
import { useDocuments, useUploadDocument, useDeleteDocument } from '@/hooks/useDocuments'
import { useState } from 'react'

export default function Dashboard() {
  const { user, logout, loading } = useRequireAuth()  // Use the auth hook properly
  const { data: documents, isLoading: documentsLoading, error } = useDocuments()
  const uploadMutation = useUploadDocument()
  const deleteMutation = useDeleteDocument()
  const [uploadProgress, setUploadProgress] = useState<number | null>(null)

  // Show loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading your documents...</p>
        </div>
      </div>
    )
  }

  // Redirect handled by useRequireAuth hook
  if (!user) {
    return null
  }

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const documentType = file.type.includes('pdf') ? 'pdf' : 
                        file.type.includes('text') ? 'txt' : 
                        file.type.includes('csv') ? 'csv' : 'unknown'

    try {
      setUploadProgress(0)
      await uploadMutation.mutateAsync({ file, documentType })
      setUploadProgress(null)
      
      // Reset file input
      event.target.value = ''
    } catch (error) {
      console.error('Upload failed:', error)
      setUploadProgress(null)
    }
  }

  const handleDeleteDocument = async (documentId: string) => {
    if (confirm('Are you sure you want to delete this document?')) {
      await deleteMutation.mutateAsync(documentId)
    }
  }

  if (documentsLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-muted-foreground">Loading your documents...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-destructive mb-4">Error</h2>
          <p className="text-muted-foreground">Failed to load documents</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <h1 className="text-2xl font-bold text-foreground">
              AI Document Platform
            </h1>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-muted-foreground">
                Welcome, {user?.email}
              </span>
              <span className={`status-indicator ${
                user?.role === 'admin' ? 'status-completed' : 'status-pending'
              }`}>
                {user?.role}
              </span>
              <button
                onClick={logout}
                className="text-sm text-destructive hover:text-destructive/80"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Upload Section */}
        <div className="mb-8">
          <h2 className="text-xl font-semibold mb-4">Upload Document</h2>
          <div className="file-upload-zone">
            <input
              type="file"
              onChange={handleFileUpload}
              accept=".pdf,.txt,.csv"
              className="hidden"
              id="file-upload"
              disabled={uploadMutation.isPending}
            />
            <label htmlFor="file-upload" className="cursor-pointer">
              <div className="text-center">
                <svg className="mx-auto h-12 w-12 text-muted-foreground" stroke="currentColor" fill="none" viewBox="0 0 48 48">
                  <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                <p className="mt-2 text-sm text-muted-foreground">
                  <span className="font-medium text-primary">Click to upload</span> or drag and drop
                </p>
                <p className="text-xs text-muted-foreground">PDF, TXT, CSV up to 10MB</p>
              </div>
            </label>
            
            {uploadMutation.isPending && (
              <div className="mt-4">
                <div className="bg-primary/20 rounded-full h-2">
                  <div 
                    className="bg-primary h-2 rounded-full transition-all duration-300"
                    style={{ width: uploadProgress ? `${uploadProgress}%` : '50%' }}
                  ></div>
                </div>
                <p className="text-sm text-muted-foreground mt-2">Uploading...</p>
              </div>
            )}
          </div>
        </div>

        {/* Documents List */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Your Documents</h2>
          
          {documents?.data?.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-muted-foreground">No documents uploaded yet</p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {documents?.data?.map((doc: any) => (
                <div key={doc.id} className="document-card">
                  <div className="flex justify-between items-start mb-2">
                    <h3 className="font-medium text-foreground truncate">
                      {doc.title}
                    </h3>
                    <span className={`status-indicator status-${doc.status}`}>
                      {doc.status}
                    </span>
                  </div>
                  
                  <p className="text-sm text-muted-foreground mb-3">
                    Type: {doc.content_type}
                  </p>
                  
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-muted-foreground">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </span>
                    
                    <div className="flex space-x-2">
                      <button className="text-xs text-primary hover:text-primary/80">
                        Query
                      </button>
                      {user?.role === 'admin' && (
                        <button
                          onClick={() => handleDeleteDocument(doc.id)}
                          className="text-xs text-destructive hover:text-destructive/80"
                          disabled={deleteMutation.isPending}
                        >
                          Delete
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}