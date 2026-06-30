import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_URL || '/api'

// ── Auth helpers ──────────────────────────────────────────────────────────────

async function authHeaders() {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ── Company ID (cached per auth session) ─────────────────────────────────────

let _companyId = null

// Reset cache on logout so a second user logging in on the same tab
// never inherits the previous user's company_id.
supabase.auth.onAuthStateChange((event) => {
  if (event === 'SIGNED_OUT') _companyId = null
})

async function getCompanyId() {
  if (_companyId) return _companyId
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) throw new Error('Not authenticated')
  const { data } = await supabase.from('users').select('company_id').eq('id', user.id).single()
  _companyId = data?.company_id
  return _companyId
}

// Exported so Dashboard can reuse without duplicating the fetch logic
export { getCompanyId }

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

async function sbAnalytics() {
  const cid = await getCompanyId()
  const todayIso = new Date(new Date().setHours(0, 0, 0, 0)).toISOString()

  const [leadsRes, todayRes, apptRes, convRes] = await Promise.all([
    supabase.from('leads').select('source, status, score').eq('company_id', cid),
    supabase.from('leads').select('id', { count: 'exact', head: true }).eq('company_id', cid).gte('created_at', todayIso),
    supabase.from('appointments').select('id', { count: 'exact', head: true }).eq('company_id', cid).gte('datetime', new Date().toISOString()).eq('status', 'scheduled'),
    supabase.from('conversations').select('id', { count: 'exact', head: true }).eq('company_id', cid),
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
  updateCompany: (data) => request('PATCH', '/companies/me', data),

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

  // Onboarding agent (Nexa)
  onboardingChat:     (data) => request('POST', '/onboarding/chat', data),
  onboardingComplete: (data) => request('POST', '/onboarding/complete', data),

  // Admin
  getAdminRequests: ()     => request('GET', '/admin/requests'),
  inviteUser:       (data) => request('POST', '/admin/invite', data),
}
