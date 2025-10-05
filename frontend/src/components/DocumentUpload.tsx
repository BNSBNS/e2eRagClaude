'use client'

import { useState } from 'react'
import { useUploadDocument } from '@/hooks/useDocuments'

export function DocumentUpload() {
  const [isDragging, setIsDragging] = useState(false)
  const uploadMutation = useUploadDocument()

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)

    const file = e.dataTransfer.files[0]
    if (file) {
      await handleFileUpload(file)
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      await handleFileUpload(file)
      e.target.value = '' // Reset input
    }
  }

  const handleFileUpload = async (file: File) => {
    const documentType = file.type.includes('pdf') ? 'pdf' : 
                        file.type.includes('text') ? 'txt' : 
                        file.type.includes('csv') ? 'csv' : 'unknown'

    try {
      await uploadMutation.mutateAsync({ file, documentType })
    } catch (error) {
      console.error('Upload failed:', error)
    }
  }

  return (
    <div
      className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
        isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300'
      }`}
      onDragOver={(e) => {
        e.preventDefault()
        setIsDragging(true)
      }}
      onDragLeave={() => setIsDragging(false)}
      onDrop={handleDrop}
    >
      <input
        type="file"
        onChange={handleFileSelect}
        accept=".pdf,.txt,.csv"
        className="hidden"
        id="file-upload"
        disabled={uploadMutation.isPending}
      />
      
      <label htmlFor="file-upload" className="cursor-pointer">
        <svg
          className="mx-auto h-12 w-12 text-gray-400"
          stroke="currentColor"
          fill="none"
          viewBox="0 0 48 48"
        >
          <path
            d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <p className="mt-2 text-sm text-gray-600">
          {uploadMutation.isPending ? (
            <span className="text-blue-600">Uploading...</span>
          ) : (
            <>
              <span className="font-medium text-blue-600">Click to upload</span> or drag and drop
            </>
          )}
        </p>
        <p className="text-xs text-gray-500 mt-1">
          PDF, TXT, or CSV up to 50MB
        </p>
      </label>

      {uploadMutation.isPending && (
        <div className="mt-4">
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '50%' }}></div>
          </div>
        </div>
      )}

      {uploadMutation.isError && (
        <p className="mt-2 text-sm text-red-600">
          Upload failed. Please try again.
        </p>
      )}
    </div>
  )
}