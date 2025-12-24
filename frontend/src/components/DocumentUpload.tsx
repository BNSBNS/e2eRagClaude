'use client'

import { useState } from 'react'
import { useUploadDocument } from '@/hooks/useDocuments'

type RAGType = 'vector' | 'graph' | 'hybrid'

export function DocumentUpload() {
  const [isDragging, setIsDragging] = useState(false)
  const [ragType, setRagType] = useState<RAGType>('vector')
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
      await uploadMutation.mutateAsync({ file, documentType, ragType })
    } catch (error) {
      console.error('Upload failed:', error)
    }
  }

  return (
    <div className="space-y-4">
      {/* RAG Type Selection */}
      <div className="bg-white border border-gray-200 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-900 mb-3">
          Choose RAG Processing Type
        </h3>
        <div className="space-y-3">
          <label className="flex items-start cursor-pointer hover:bg-gray-50 p-2 rounded">
            <input
              type="radio"
              name="ragType"
              value="vector"
              checked={ragType === 'vector'}
              onChange={(e) => setRagType(e.target.value as RAGType)}
              className="mt-1 mr-3"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">🔍 Vector RAG</div>
              <p className="text-sm text-gray-600">
                Fast semantic search. Best for Q&A and finding similar content.
              </p>
              <p className="text-xs text-gray-500 mt-1">Uses: OpenAI embeddings + ChromaDB</p>
            </div>
          </label>

          <label className="flex items-start cursor-pointer hover:bg-gray-50 p-2 rounded">
            <input
              type="radio"
              name="ragType"
              value="graph"
              checked={ragType === 'graph'}
              onChange={(e) => setRagType(e.target.value as RAGType)}
              className="mt-1 mr-3"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">🕸️ Graph RAG</div>
              <p className="text-sm text-gray-600">
                Relationship reasoning. Best for understanding connections and &quot;how/why&quot; questions.
              </p>
              <p className="text-xs text-gray-500 mt-1">Uses: Entity extraction + Neo4j graph</p>
            </div>
          </label>

          <label className="flex items-start cursor-pointer hover:bg-gray-50 p-2 rounded">
            <input
              type="radio"
              name="ragType"
              value="hybrid"
              checked={ragType === 'hybrid'}
              onChange={(e) => setRagType(e.target.value as RAGType)}
              className="mt-1 mr-3"
            />
            <div className="flex-1">
              <div className="font-medium text-gray-900">⚡ Hybrid RAG</div>
              <p className="text-sm text-gray-600">
                Both approaches for maximum accuracy. Best for complex analysis.
              </p>
              <p className="text-xs text-gray-500 mt-1">Note: 2x processing time and storage</p>
            </div>
          </label>
        </div>
      </div>

      {/* File Upload Area */}
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
              <span className="text-blue-600">Uploading with {ragType} RAG...</span>
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
    </div>
  )
}
