import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_URL || '/api'

async function authHeaders() {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request(method, path, body, isFormData = false) {
  const headers = await authHeaders()
  if (!isFormData) headers['Content-Type'] = 'application/json'

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
  })

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }

  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // Leads
  getLeads: (params = {}) => {
    const q = new URLSearchParams(params).toString()
    return request('GET', `/leads/?${q}`)
  },
  getLead: (id) => request('GET', `/leads/${id}`),
  createLead: (data) => request('POST', '/leads/', data),
  updateLead: (id, data) => request('PATCH', `/leads/${id}`, data),
  updateLeadStatus: (id, status) => request('PATCH', `/leads/${id}/status`, { status }),
  deleteLead: (id) => request('DELETE', `/leads/${id}`),

  // Appointments
  getAppointments: () => request('GET', '/leads/appointments/upcoming'),
  createAppointment: (data) => request('POST', '/leads/appointments', data),
  updateAppointment: (id, data) => request('PATCH', `/leads/appointments/${id}`, data),
  deleteAppointment: (id) => request('DELETE', `/leads/appointments/${id}`),

  // Analytics
  getAnalytics: () => request('GET', '/leads/analytics/summary'),

  // Properties
  getProperties: () => request('GET', '/properties/'),
  getProperty: (id) => request('GET', `/properties/${id}`),
  createProperty: (data) => request('POST', '/properties/', data),
  updateProperty: (id, data) => request('PATCH', `/properties/${id}`, data),
  deleteProperty: (id) => request('DELETE', `/properties/${id}`),

  // RAG
  getDocuments: () => request('GET', '/rag/documents'),
  ingestText: (data) => request('POST', '/rag/ingest/text', data),
  deleteDocument: (id) => request('DELETE', `/rag/documents/${id}`),
  getJobStatus: (jobId) => request('GET', `/rag/status/${jobId}`),
  ingestFile: (formData) => request('POST', '/rag/ingest', formData, true),
}
