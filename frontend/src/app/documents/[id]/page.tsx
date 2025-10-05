'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { useDocument } from '@/hooks/useDocuments'
import { ChatInterface } from '@/components/chat/ChatInterface'
import { TeacherInterface } from '@/components/TeacherInterface'

export default function DocumentDetailPage() {
  const params = useParams()
  const documentId = params?.id as string // Add optional chaining
  const { data: document, isLoading } = useDocument(documentId)
  const [activeTab, setActiveTab] = useState<'chat' | 'teacher'>('chat')

  // Add guard for missing params
  if (!params || !params.id) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Invalid Document</h2>
          <a href="/dashboard" className="text-blue-600 hover:underline">
            Back to Dashboard
          </a>
        </div>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  if (!document) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Document Not Found</h2>
          <a href="/dashboard" className="text-blue-600 hover:underline">
            Back to Dashboard
          </a>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div>
              <a href="/dashboard" className="text-blue-600 hover:underline text-sm">
                ← Back to Dashboard
              </a>
              <h1 className="text-2xl font-bold text-gray-900 mt-2">{document.title}</h1>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="mb-4 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            <button
              onClick={() => setActiveTab('chat')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'chat'
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Q&A Chat
            </button>
            <button
              onClick={() => setActiveTab('teacher')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${
                activeTab === 'teacher'
                  ? 'border-green-500 text-green-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              Teacher Mode
            </button>
          </nav>
        </div>

        {/* Content */}
        <div className="bg-white rounded-lg shadow" style={{ height: 'calc(100vh - 300px)' }}>
          {activeTab === 'chat' ? (
            <ChatInterface documentId={documentId} />
          ) : (
            <TeacherInterface documentId={documentId} />
          )}
        </div>
      </main>
    </div>
  )
}