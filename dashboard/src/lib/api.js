import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_URL || '/api'

// ── Auth helpers ──────────────────────────────────────────────────────────────

async function authHeaders() {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ── Company ID (cached for the session) ──────────────────────────────────────

let _companyId = null
async function getCompanyId() {
  if (_companyId) return _companyId
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error('Not authenticated')
  const { data } = await supabase.from('users').select('company_id').eq('id', user.id).single()
  _companyId = data?.company_id
  return _companyId
}

// ── HF API request (writes / business logic only) ────────────────────────────

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

// ── Supabase direct reads (fast — no HF roundtrip) ───────────────────────────

async function sbLeads(params = {}) {
  const cid = await getCompanyId()
  let q = supabase.from('leads')
    .select('*, conversations(id, channel, started_at)')
    .eq('company_id', cid)
    .order('created_at', { ascending: false })
    .limit(params.limit || 50)
  if (params.status) q = q.eq('status', params.status)
  if (params.source) q = q.eq('source', params.source)
  const { data, error } = await q
  if (error) throw new Error(error.message)
  return data
}

async function sbLead(id) {
  const cid = await getCompanyId()
  const { data, error } = await supabase.from('leads')
    .select('*, conversations(*), appointments(*)')
    .eq('id', id)
    .eq('company_id', cid)
    .single()
  if (error) throw new Error(error.message)
  return data
}

async function sbAppointments() {
  const cid = await getCompanyId()
  const { data, error } = await supabase.from('appointments')
    .select('*, leads(name, phone), properties(title, address)')
    .eq('company_id', cid)
    .gte('datetime', new Date().toISOString())
    .order('datetime')
    .limit(20)
  if (error) throw new Error(error.message)
  return data
}

async function sbProperties() {
  const cid = await getCompanyId()
  const { data, error } = await supabase.from('properties')
    .select('*')
    .eq('company_id', cid)
    .order('created_at', { ascending: false })
  if (error) throw new Error(error.message)
  return data
}

async function sbDocuments() {
  const cid = await getCompanyId()
  const { data, error } = await supabase.from('documents')
    .select('*')
    .eq('company_id', cid)
    .order('created_at', { ascending: false })
  if (error) throw new Error(error.message)
  return data
}

// ── Exported API ──────────────────────────────────────────────────────────────

export const api = {
  // Leads — reads: Supabase direct, writes: HF API
  getLeads:         (params = {}) => sbLeads(params),
  getLead:          (id)          => sbLead(id),
  createLead:       (data)        => request('POST', '/leads/', data),
  updateLead:       (id, data)    => request('PATCH', `/leads/${id}`, data),
  updateLeadStatus: (id, status)  => request('PATCH', `/leads/${id}/status`, { status }),
  deleteLead:       (id)          => request('DELETE', `/leads/${id}`),

  // Appointments — reads: Supabase direct, writes: HF API
  getAppointments:    ()         => sbAppointments(),
  createAppointment:  (data)     => request('POST', '/leads/appointments', data),
  updateAppointment:  (id, data) => request('PATCH', `/leads/appointments/${id}`, data),
  deleteAppointment:  (id)       => request('DELETE', `/leads/appointments/${id}`),

  // Analytics — computed aggregates, must go through HF
  getAnalytics: () => request('GET', '/leads/analytics/summary'),

  // Properties — reads: Supabase direct, writes: HF API (triggers RAG ingest)
  getProperties:   ()         => sbProperties(),
  createProperty:  (data)     => request('POST', '/properties/', data),
  updateProperty:  (id, data) => request('PATCH', `/properties/${id}`, data),
  deleteProperty:  (id)       => request('DELETE', `/properties/${id}`),

  // Documents — reads: Supabase direct, writes: HF API (RAG processing)
  getDocuments:  ()          => sbDocuments(),
  ingestText:    (data)      => request('POST', '/rag/ingest/text', data),
  deleteDocument:(id)        => request('DELETE', `/rag/documents/${id}`),
  getJobStatus:  (jobId)     => request('GET', `/rag/status/${jobId}`),
  ingestFile:    (formData)  => request('POST', '/rag/ingest', formData, true),
}
