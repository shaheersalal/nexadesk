import { supabase } from './supabase'

import { API_BASE as BASE } from './apiBase'

// ── Auth helpers ──────────────────────────────────────────────────────────────

async function authHeaders() {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ── Company ID (cached per auth session) ─────────────────────────────────────

let _companyId = null
let _accessibleCompanies = null
const SELECTED_COMPANY_KEY = 'nexadesk_selected_company'

supabase.auth.onAuthStateChange((event) => {
  if (event === 'SIGNED_OUT') {
    _companyId = null
    _accessibleCompanies = null
    localStorage.removeItem(SELECTED_COMPANY_KEY)
  }
})

async function getCompanyId() {
  if (_companyId) return _companyId
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error('Not authenticated')
  const { data } = await supabase.from('users').select('company_id').eq('id', user.id).single()
  _companyId = data?.company_id
  return _companyId
}

// Exported so Dashboard and Layout can reuse without duplicating the fetch logic
export { getCompanyId }

// ── Phase 6: company switcher (parent/child multi-tenant) ─────────────────────
// Returns the company the user has manually selected via the switcher, or null
// (= aggregate across all accessible companies via RLS).
export function getSelectedCompanyId() {
  return localStorage.getItem(SELECTED_COMPANY_KEY) || null
}

export function setSelectedCompanyId(id) {
  if (id) localStorage.setItem(SELECTED_COMPANY_KEY, id)
  else localStorage.removeItem(SELECTED_COMPANY_KEY)
}

// Returns all company rows the current user can access (self + children for a
// parent account, self only for normal/child accounts). RLS scopes this query.
// Result is cached for the auth session lifetime.
export async function getAccessibleCompanies() {
  if (_accessibleCompanies) return _accessibleCompanies
  const { data, error } = await supabase
    .from('companies')
    .select('id, name, parent_company_id')
    .order('name')
  if (error) throw new Error(error.message)
  _accessibleCompanies = data || []
  return _accessibleCompanies
}

// ── HF API request (writes / business logic only) ────────────────────────────

async function request(method, path, body, isFormData = false) {
  const headers = await authHeaders()
  if (!isFormData) headers['Content-Type'] = 'application/json'
  // No timeout on file uploads (isFormData) — ingestion of larger files can
  // legitimately take longer. Everything else gets a 5s cap so a backend
  // outage shows as a fast, honest failure instead of an indefinite hang.
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
    signal: isFormData ? undefined : AbortSignal.timeout(5000),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || 'Request failed')
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Supabase direct reads (fast — no HF roundtrip) ────────────────────────────
// Phase 6: company_id filter removed from list queries. The updated RLS policy
// (accessible_company_ids()) scopes each query to exactly the right rows:
//   • single-company / child users  → only their own company's rows (unchanged)
//   • parent account, no switcher   → aggregated across self + all children
//   • parent account, switcher set  → narrowed to the selected company id

async function sbLeads(params = {}) {
  const selectedId = getSelectedCompanyId()
  let q = supabase.from('leads')
    .select('*, conversations(id, channel, started_at)')
    .order('created_at', { ascending: false })
    .limit(params.limit || 50)
  if (selectedId) q = q.eq('company_id', selectedId)
  if (params.status) q = q.eq('status', params.status)
  if (params.source) q = q.eq('source', params.source)
  const { data, error } = await q
  if (error) throw new Error(error.message)
  return data
}

async function sbLead(id) {
  // RLS scopes single-record reads to accessible companies automatically.
  const { data, error } = await supabase.from('leads')
    .select('*, conversations(*), appointments(*)')
    .eq('id', id)
    .single()
  if (error) throw new Error(error.message)
  return data
}

async function sbAppointments() {
  const selectedId = getSelectedCompanyId()
  let q = supabase.from('appointments')
    .select('*, leads(name, phone), properties(title, address)')
    .gte('datetime', new Date().toISOString())
    .order('datetime')
    .limit(20)
  if (selectedId) q = q.eq('company_id', selectedId)
  const { data, error } = await q
  if (error) throw new Error(error.message)
  return data
}

async function sbProperties() {
  const selectedId = getSelectedCompanyId()
  let q = supabase.from('properties')
    .select('*')
    .order('created_at', { ascending: false })
  if (selectedId) q = q.eq('company_id', selectedId)
  const { data, error } = await q
  if (error) throw new Error(error.message)
  return data
}

async function sbDocuments() {
  const selectedId = getSelectedCompanyId()
  let q = supabase.from('documents')
    .select('*')
    .order('created_at', { ascending: false })
  if (selectedId) q = q.eq('company_id', selectedId)
  const { data, error } = await q
  if (error) throw new Error(error.message)
  return data
}

async function sbAnalytics() {
  const selectedId = getSelectedCompanyId()
  const todayIso = new Date(new Date().setHours(0, 0, 0, 0)).toISOString()

  function f(q) { return selectedId ? q.eq('company_id', selectedId) : q }

  const [leadsRes, todayRes, apptRes, convRes] = await Promise.all([
    f(supabase.from('leads').select('source, status, score')),
    f(supabase.from('leads').select('id', { count: 'exact', head: true }).gte('created_at', todayIso)),
    f(supabase.from('appointments').select('id', { count: 'exact', head: true }).gte('datetime', new Date().toISOString()).eq('status', 'scheduled')),
    f(supabase.from('conversations').select('id', { count: 'exact', head: true })),
  ])

  if (leadsRes.error) throw new Error(leadsRes.error.message)

  const leads = leadsRes.data || []
  const by_status = {}
  const by_source = {}
  let totalScore = 0
  for (const l of leads) {
    by_status[l.status] = (by_status[l.status] || 0) + 1
    by_source[l.source] = (by_source[l.source] || 0) + 1
    totalScore += (l.score || 0)
  }

  return {
    total_leads: leads.length,
    avg_score: leads.length ? Math.round(totalScore / leads.length) : 0,
    leads_today: todayRes.count || 0,
    appointments_upcoming: apptRes.count || 0,
    total_conversations: convRes.count || 0,
    leads_by_status: by_status,
    leads_by_source: by_source,
  }
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

  // Analytics — computed client-side from Supabase (fast, no HF roundtrip)
  getAnalytics: () => sbAnalytics(),

  // Company — writes: HF API (RLS has no UPDATE policy for direct writes)
  updateCompany:           (data) => request('PATCH', '/companies/me', data),
  listAccessibleCompanies: ()     => request('GET', '/companies/accessible'),
  createChildCompany:      (data) => request('POST', '/companies/child', data),

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
  ingestVoice:   (formData)  => request('POST', '/rag/ingest/voice', formData, true),

  // Assistant
  assistantChat:   (data) => request('POST', '/assistant/chat', data),
  assistantNotify: (data) => request('POST', '/assistant/notify', data),

  // Onboarding
  onboardingComplete: (data) => request('POST', '/onboarding/complete', data),

  // Admin
  getAdminRequests: ()     => request('GET', '/admin/requests'),
  inviteUser:       (data) => request('POST', '/admin/invite', data),
}
