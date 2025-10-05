import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

class APIClient {
  private client

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
    })

    // Add auth token to requests
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('access_token')
      if (token) {
        config.headers.Authorization = `Bearer ${token}`
      }
      return config
    })
  }

  async get(url: string) {
    return this.client.get(url)
  }

  async post(url: string, data?: any, config?: any) {
    return this.client.post(url, data, config)
  }

  async delete(url: string) {
    return this.client.delete(url)
  }

  // Document methods
  async getDocuments() {
    const response = await this.get('/api/documents')
    return response.data
  }

  async uploadDocument(file: File, documentType: string) {
    const formData = new FormData()
    formData.append('file', file)
    formData.append('document_type', documentType)
    
    return this.client.post('/api/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }

  async deleteDocument(documentId: string) {
    return this.delete(`/api/documents/${documentId}`)
  }

  async queryDocument(documentId: string, question: string, method: 'rag' | 'graph') {
    const response = await this.post(`/api/ai/query/${documentId}`, { 
      question, 
      method 
    })
    return response.data
  }
}

export const apiClient = new APIClient()