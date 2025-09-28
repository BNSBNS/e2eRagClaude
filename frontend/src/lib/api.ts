// src/lib/api.ts - FIXED TypeScript headers issue
'use client'

class APIClient {
  private baseURL: string;

  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  }

  private getAuthHeaders(): Record<string, string> {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('access_token');
      return token ? { 'Authorization': `Bearer ${token}` } : {};
    }
    return {};
  }

  async get(endpoint: string) {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.getAuthHeaders(),
    };

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        // Token expired, redirect to login
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
      }
      throw new Error(`API Error: ${response.status}`);
    }

    return { data: await response.json() };
  }

  async post(endpoint: string, data: any) {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.getAuthHeaders(),
    };

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      if (response.status === 401) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
      }
      throw new Error(`API Error: ${response.status}`);
    }

    return { data: await response.json() };
  }

  async delete(endpoint: string) {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...this.getAuthHeaders(),
    };

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method: 'DELETE',
      headers,
    });

    if (!response.ok) {
      if (response.status === 401) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
      }
      throw new Error(`API Error: ${response.status}`);
    }

    return { data: await response.json() };
  }

  // Document-specific methods
  async uploadDocument(file: File, documentType: string) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('document_type', documentType);

    // For FormData, don't include Content-Type header
    const authHeaders = this.getAuthHeaders();
    const headers: Record<string, string> = { ...authHeaders };

    const response = await fetch(`${this.baseURL}/api/documents/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });

    if (!response.ok) {
      if (response.status === 401) {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token');
          window.location.href = '/login';
        }
      }
      throw new Error(`Upload failed: ${response.status}`);
    }

    return await response.json();
  }

  async getDocuments() {
    return this.get('/api/documents');
  }

  async deleteDocument(documentId: string) {
    return this.delete(`/api/documents/${documentId}`);
  }

  async queryDocument(documentId: string, query: string, method: 'rag' | 'graph') {
    return this.post(`/api/documents/${documentId}/query`, { query, method });
  }
}

export const apiClient = new APIClient();