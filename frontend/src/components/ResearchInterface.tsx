'use client'

import { useState } from 'react'

interface ResearchInterfaceProps {
  documentId: string
}

export function ResearchInterface({ documentId }: ResearchInterfaceProps) {
  const [query, setQuery] = useState('')
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  const handleResearch = async () => {
    if (!query.trim()) return
    
    setLoading(true)
    try {
      const response = await fetch(`http://localhost:8000/api/research/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('access_token')}`
        },
        body: JSON.stringify({
          document_id: parseInt(documentId),
          query: query
        })
      })
      
      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error('Research failed:', error)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="p-6">
      <h3 className="text-lg font-semibold mb-4">Autonomous Research Agent</h3>
      
      <div className="mb-4">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What would you like to research?"
          className="w-full px-4 py-2 border rounded-lg"
        />
        <button
          onClick={handleResearch}
          disabled={loading}
          className="mt-2 px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
        >
          {loading ? 'Researching...' : 'Start Research'}
        </button>
      </div>

      {result && (
        <div className="space-y-4">
          <div className="bg-blue-50 p-4 rounded-lg">
            <h4 className="font-semibold text-blue-900 mb-2">Research Plan</h4>
            <ol className="list-decimal list-inside space-y-1">
              {result.plan.map((step: string, i: number) => (
                <li key={i} className="text-blue-800">{step}</li>
              ))}
            </ol>
          </div>

          <div className="bg-green-50 p-4 rounded-lg">
            <h4 className="font-semibold text-green-900 mb-2">Findings</h4>
            {result.findings.map((finding: any, i: number) => (
              <div key={i} className="mb-2">
                <p className="font-medium">{finding.step}</p>
                <p className="text-sm text-green-800">{finding.finding}</p>
              </div>
            ))}
          </div>

          <div className="bg-white border p-4 rounded-lg">
            <h4 className="font-semibold mb-2">Final Answer</h4>
            <p className="whitespace-pre-wrap">{result.answer}</p>
            <p className="text-xs text-gray-500 mt-2">Cost: ${result.cost.toFixed(4)}</p>
          </div>
        </div>
      )}
    </div>
  )
}