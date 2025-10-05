'use client'

import { useRequireAuth } from '@/hooks/useAuth'
import { DocumentUpload } from '@/components/DocumentUpload'
import { DocumentList } from '@/components/DocumentList'

export default function DashboardPage() {
  const { user, loading } = useRequireAuth()

  if (loading || !user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">
              AI Document Platform
            </h1>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">{user.email}</span>
              <span className={`px-2 py-1 text-xs rounded ${
                user.role === 'admin' ? 'bg-purple-100 text-purple-800' : 'bg-blue-100 text-blue-800'
              }`}>
                {user.role}
              </span>
              <button
                onClick={() => {
                  localStorage.removeItem('access_token')
                  window.location.href = '/login'
                }}
                className="px-4 py-2 text-sm text-white bg-red-600 rounded hover:bg-red-700"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Upload Section */}
        <section className="mb-8">
          <h2 className="text-xl font-semibold mb-4 text-gray-900">Upload Document</h2>
          <DocumentUpload />
        </section>

        {/* Documents List */}
        <section>
          <h2 className="text-xl font-semibold mb-4 text-gray-900">Your Documents</h2>
          <DocumentList />
        </section>
      </main>
    </div>
  )
}