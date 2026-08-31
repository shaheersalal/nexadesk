import { useState, useEffect, useCallback } from 'react'
import {
  Plus, Trash2, Play, ChevronDown, ChevronUp, Check, X,
  Loader2, Copy, Plug, Link2, Link2Off, RefreshCw, Key, Terminal, Zap,
} from 'lucide-react'

import { API_BASE as BASE } from '../lib/apiBase'

const ALL_EVENTS = [
  { id: 'lead.created',        label: 'New Lead',            desc: 'Fired when a lead is captured via chat, voice, or manually' },
  { id: 'lead.status_changed', label: 'Lead Status Changed', desc: 'Fired when a lead moves through the pipeline' },
  { id: 'appointment.booked',  label: 'Appointment Booked',  desc: 'Fired when a viewing is scheduled' },
  { id: 'call.ended',          label: 'Call Ended',          desc: 'Fired when an AI phone call finishes' },
]

const CRM_PROVIDERS = [
  { id: 'hubspot',     name: 'HubSpot',     color: '#ff7a59', available: true  },
  { id: 'zoho',        name: 'Zoho CRM',    color: '#e42527', available: true  },
  { id: 'gohighlevel', name: 'GoHighLevel', color: '#01a58b', available: false },
  { id: 'pipedrive',   name: 'Pipedrive',   color: '#26292c', available: false },
  { id: 'salesforce',  name: 'Salesforce',  color: '#00a1e0', available: false },
]

const ALL_SCOPES = [
  { id: 'leads:read',        label: 'Read leads' },
  { id: 'leads:write',       label: 'Create leads' },
  { id: 'appointments:read', label: 'Read appointments' },
  { id: 'properties:read',   label: 'Read properties' },
]

// ── Auth helpers ──────────────────────────────────────────────────────────────

async function authHeaders() {
  const { supabase } = await import('../lib/supabase')
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token
    ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }
    : { 'Content-Type': 'application/json' }
}

async function apiFetch(method, path, body) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}${path}`, {
    method, headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Request failed')
  return data
}

// ── Shared UI ─────────────────────────────────────────────────────────────────

function CopyButton({ text, className = '' }) {
  const [copied, setCopied] = useState(false)
  function copy() { navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }
  return (
    <button onClick={copy}
      className={`flex items-center gap-1 text-xs font-semibold px-2.5 py-1.5 rounded-lg transition-colors ${className}`}>
      {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

function SectionHeader({ icon: Icon, title, description }) {
  return (
    <div className="flex items-start gap-3 pb-3 border-b border-gray-100">
      <div className="w-9 h-9 rounded-lg bg-accent/10 flex items-center justify-center flex-shrink-0 mt-0.5">
        <Icon className="w-4 h-4 text-accent-ink" />
      </div>
      <div>
        <h2 className="text-base font-semibold text-gray-900">{title}</h2>
        <p className="text-xs text-gray-400 mt-0.5">{description}</p>
      </div>
    </div>
  )
}

// ── ── SECTION 1: WEBHOOKS ── ──

function EventSelector({ selected, onChange }) {
  return (
    <div className="space-y-2">
      {ALL_EVENTS.map(ev => (
        <label key={ev.id} className="flex items-start gap-3 cursor-pointer group">
          <div
            onClick={() => onChange(selected.includes(ev.id) ? selected.filter(e => e !== ev.id) : [...selected, ev.id])}
            className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors
              ${selected.includes(ev.id) ? 'bg-accent border-accent' : 'border-gray-300 group-hover:border-accent'}`}>
            {selected.includes(ev.id) && <Check className="w-2.5 h-2.5 text-white" />}
          </div>
          <div>
            <p className="text-sm font-medium text-gray-800">{ev.label}</p>
            <p className="text-xs text-gray-400">{ev.desc}</p>
          </div>
        </label>
      ))}
    </div>
  )
}

function AddWebhookForm({ onCreated, onCancel }) {
  const [url, setUrl] = useState('')
  const [events, setEvents] = useState(['lead.created'])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [secret, setSecret] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (!events.length) { setError('Select at least one event.'); return }
    setLoading(true); setError('')
    try {
      const result = await apiFetch('POST', '/integrations/webhooks', { url, events })
      setSecret(result.secret); onCreated(result)
    } catch (err) { setError(err.message) }
    finally { setLoading(false) }
  }

  if (secret) return (
    <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-3">
      <p className="text-sm font-semibold text-amber-800">Webhook created — save your signing secret</p>
      <p className="text-xs text-amber-700">Use this to verify NexaDesk requests. It will <strong>not be shown again</strong>.</p>
      <div className="flex items-center gap-2">
        <code className="flex-1 bg-surface border border-amber-300 rounded-lg px-3 py-2 text-xs font-mono text-gray-800 truncate">{secret}</code>
        <CopyButton text={secret} className="text-amber-800 bg-amber-100 hover:bg-amber-200 border border-amber-300" />
      </div>
      <button onClick={onCancel} className="text-xs font-semibold text-amber-700 hover:text-amber-900">Done →</button>
    </div>
  )

  return (
    <form onSubmit={submit} className="bg-gray-50 border border-gray-200 rounded-xl p-5 space-y-4">
      <div>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Endpoint URL</label>
        <input type="url" required value={url} onChange={e => setUrl(e.target.value)}
          placeholder="https://your-crm.com/webhooks/nexadesk"
          className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
      </div>
      <div>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Events to subscribe</label>
        <EventSelector selected={events} onChange={setEvents} />
      </div>
      {error && <p className="text-red-500 text-xs">{error}</p>}
      <div className="flex gap-2 pt-1">
        <button type="submit" disabled={loading}
          className="flex items-center gap-2 bg-accent text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-accent-dark disabled:opacity-50 transition-colors">
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
          {loading ? 'Creating…' : 'Create Webhook'}
        </button>
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700 px-3 py-2">Cancel</button>
      </div>
    </form>
  )
}

function LogDrawer({ webhookId, onClose }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    apiFetch('GET', `/integrations/webhooks/${webhookId}/logs`)
      .then(setLogs).catch(() => {}).finally(() => setLoading(false))
  }, [webhookId])
  return (
    <div className="mt-3 border border-gray-200 rounded-xl overflow-hidden">
      <div className="bg-gray-50 px-4 py-2.5 flex items-center justify-between border-b border-gray-200">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Delivery Log</p>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X className="w-4 h-4" /></button>
      </div>
      <div className="divide-y divide-gray-100 max-h-64 overflow-y-auto">
        {loading && <div className="p-4 text-center"><Loader2 className="w-4 h-4 animate-spin text-gray-400 mx-auto" /></div>}
        {!loading && !logs.length && <p className="p-4 text-sm text-gray-400 text-center">No deliveries yet</p>}
        {logs.map(log => (
          <div key={log.id} className="px-4 py-3 flex items-center gap-3">
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${log.delivered_at ? 'bg-green-400' : log.next_retry_at ? 'bg-amber-400' : 'bg-red-400'}`} />
            <div className="flex-1 min-w-0">
              <p className="text-xs font-medium text-gray-700">{log.event}</p>
              <p className="text-xs text-gray-400 truncate">
                {log.delivered_at ? `Delivered · HTTP ${log.status_code}` :
                 log.next_retry_at ? `Retry scheduled · attempt ${log.attempts}` :
                 `Failed · ${log.error || `HTTP ${log.status_code}`}`}
              </p>
            </div>
            <p className="text-xs text-gray-400 flex-shrink-0">{new Date(log.created_at).toLocaleTimeString()}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

function WebhookRow({ webhook, onDelete }) {
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [logsOpen, setLogsOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function test() {
    setTesting(true); setTestResult(null)
    try { await apiFetch('POST', `/integrations/webhooks/${webhook.id}/test`); setTestResult('sent') }
    catch { setTestResult('error') }
    finally { setTesting(false); setTimeout(() => setTestResult(null), 3000) }
  }

  async function del() {
    if (!window.confirm('Delete this webhook?')) return
    setDeleting(true)
    try { await apiFetch('DELETE', `/integrations/webhooks/${webhook.id}`); onDelete(webhook.id) }
    finally { setDeleting(false) }
  }

  return (
    <div className="border border-gray-200 rounded-xl p-4 space-y-3">
      <div className="flex items-start gap-3">
        <div className={`mt-1 w-2 h-2 rounded-full flex-shrink-0 ${webhook.active ? 'bg-green-400' : 'bg-gray-300'}`} />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-gray-800 truncate">{webhook.url}</p>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            {(webhook.events || []).map(ev => {
              const found = ALL_EVENTS.find(e => e.id === ev)
              return <span key={ev} className="text-xs bg-blue-50 text-blue-700 border border-blue-100 rounded-full px-2 py-0.5">{found?.label || ev}</span>
            })}
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button onClick={test} disabled={testing} title="Send a test event"
            className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-50">
            {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            {testResult === 'sent' ? 'Sent ✓' : testResult === 'error' ? 'Error' : 'Test'}
          </button>
          <button onClick={() => setLogsOpen(o => !o)}
            className="text-xs font-medium text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1">
            Logs {logsOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          <button onClick={del} disabled={deleting}
            className="text-red-400 hover:text-red-700 hover:bg-red-50 p-1.5 rounded-lg transition-colors disabled:opacity-50">
            {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          </button>
        </div>
      </div>
      {logsOpen && <LogDrawer webhookId={webhook.id} onClose={() => setLogsOpen(false)} />}
    </div>
  )
}

function WebhooksSection() {
  const [webhooks, setWebhooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    apiFetch('GET', '/integrations/webhooks')
      .then(setWebhooks).catch(() => {}).finally(() => setLoading(false))
  }, [])

  return (
    <section className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <SectionHeader icon={Plug} title="Webhooks"
          description={<>NexaDesk POSTs JSON to your URL in real time. Verify with the <code className="bg-gray-100 text-gray-600 px-1 rounded">X-NexaDesk-Signature</code> header.</>} />
        {!adding && (
          <button onClick={() => setAdding(true)}
            className="flex items-center gap-1.5 text-sm font-semibold text-white bg-accent hover:bg-accent-dark px-4 py-2 rounded-lg transition-colors flex-shrink-0 mt-0.5">
            <Plus className="w-4 h-4" /> Add
          </button>
        )}
      </div>
      {adding && <AddWebhookForm onCreated={w => setWebhooks(p => [w, ...p])} onCancel={() => setAdding(false)} />}
      {loading && <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>}
      {!loading && !webhooks.length && !adding && (
        <div className="text-center py-10 border-2 border-dashed border-gray-200 rounded-xl">
          <Plug className="w-8 h-8 text-gray-300 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-500">No webhooks yet</p>
          <p className="text-xs text-gray-400 mt-1">Add an endpoint to receive real-time events.</p>
        </div>
      )}
      <div className="space-y-3">
        {webhooks.map(w => <WebhookRow key={w.id} webhook={w} onDelete={id => setWebhooks(p => p.filter(x => x.id !== id))} />)}
      </div>
    </section>
  )
}

// ── ── SECTION 2: CRM CONNECTIONS ── ──

function CrmSection() {
  const [connections, setConnections] = useState([])
  const [loading, setLoading] = useState(true)
  const [connecting, setConnecting] = useState(null)
  const [syncing, setSyncing] = useState(null)
  const [disconnecting, setDisconnecting] = useState(null)
  const [toast, setToast] = useState(null)

  function showToast(msg, type = 'success') {
    setToast({ msg, type }); setTimeout(() => setToast(null), 4000)
  }

  const load = useCallback(async () => {
    try { const d = await apiFetch('GET', '/integrations/crm/connections'); setConnections(d || []) }
    catch {} finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const connected = params.get('connected')
    const error = params.get('error')
    if (connected || error) {
      window.history.replaceState({}, '', window.location.pathname)
      if (connected) { showToast(`${CRM_PROVIDERS.find(p => p.id === connected)?.name || connected} connected!`); load() }
      if (error) {
        const msgs = { state_expired: 'Session expired — try again.', auth_failed: 'Authentication failed.', unknown_provider: 'Unknown CRM.' }
        showToast(msgs[error] || error, 'error')
      }
    }
  }, [])

  async function connect(provider) {
    setConnecting(provider)
    try {
      const data = await apiFetch('GET', `/integrations/crm/connect/${provider}`)
      window.location.href = data.auth_url
    } catch (err) {
      showToast(err.message.includes('not configured') ? `Add ${provider.toUpperCase()}_CLIENT_ID to your .env first` : err.message, 'error')
      setConnecting(null)
    }
  }

  async function disconnect(provider) {
    if (!window.confirm(`Disconnect ${CRM_PROVIDERS.find(p => p.id === provider)?.name}?`)) return
    setDisconnecting(provider)
    try { await apiFetch('DELETE', `/integrations/crm/${provider}`); setConnections(prev => prev.filter(c => c.provider !== provider)); showToast('Disconnected') }
    catch (err) { showToast(err.message, 'error') }
    finally { setDisconnecting(null) }
  }

  async function sync(provider) {
    setSyncing(provider)
    try {
      const r = await apiFetch('POST', `/integrations/crm/sync/${provider}`)
      showToast(`Synced ${r.synced} leads to ${CRM_PROVIDERS.find(p => p.id === provider)?.name}${r.errors ? ` (${r.errors} errors)` : ''}`)
    } catch (err) { showToast(err.message, 'error') }
    finally { setSyncing(null) }
  }

  const connMap = Object.fromEntries(connections.map(c => [c.provider, c]))

  return (
    <section className="space-y-4">
      <SectionHeader icon={Link2} title="CRM Connections"
        description="One-click OAuth — NexaDesk pushes leads, status changes, and appointments to your CRM automatically." />

      {toast && (
        <div className={`flex items-center gap-2 px-4 py-3 rounded-xl text-sm font-medium border ${toast.type === 'error' ? 'bg-red-50 text-red-700 border-red-200' : 'bg-green-50 text-green-700 border-green-200'}`}>
          {toast.type === 'error' ? <X className="w-4 h-4 flex-shrink-0" /> : <Check className="w-4 h-4 flex-shrink-0" />}
          {toast.msg}
        </div>
      )}

      {loading
        ? <div className="flex justify-center py-8"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>
        : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {CRM_PROVIDERS.map(p => {
              const conn = connMap[p.id]
              return (
                <div key={p.id} className={`border rounded-xl p-4 flex items-center gap-3 ${p.available ? 'border-gray-200' : 'border-gray-100 opacity-50'}`}>
                  <div className="w-10 h-10 rounded-lg flex items-center justify-center text-white text-sm font-bold flex-shrink-0"
                    style={{ backgroundColor: p.color }}>{p.name[0]}</div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900">{p.name}</p>
                    {conn
                      ? <p className="text-xs text-green-600 font-medium">{conn.account_name || 'Connected'}</p>
                      : <p className="text-xs text-gray-400">{p.available ? 'Not connected' : 'Coming soon'}</p>}
                  </div>
                  {p.available && (conn ? (
                    <div className="flex items-center gap-1.5 flex-shrink-0">
                      <button onClick={() => sync(p.id)} disabled={syncing === p.id}
                        className="text-xs font-medium text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 px-2 py-1.5 rounded-lg transition-colors disabled:opacity-50 flex items-center gap-1">
                        {syncing === p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5" />}
                        {syncing === p.id ? 'Syncing…' : 'Sync'}
                      </button>
                      <button onClick={() => disconnect(p.id)} disabled={disconnecting === p.id}
                        className="text-red-400 hover:text-red-700 hover:bg-red-50 p-1.5 rounded-lg transition-colors disabled:opacity-50">
                        {disconnecting === p.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link2Off className="w-4 h-4" />}
                      </button>
                    </div>
                  ) : (
                    <button onClick={() => connect(p.id)} disabled={connecting === p.id}
                      className="flex items-center gap-1.5 text-xs font-semibold text-white bg-accent hover:bg-accent-dark px-3 py-1.5 rounded-lg transition-colors disabled:opacity-60">
                      {connecting === p.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Link2 className="w-3.5 h-3.5" />}
                      {connecting === p.id ? 'Redirecting…' : 'Connect'}
                    </button>
                  ))}
                </div>
              )
            })}
          </div>
        )}
    </section>
  )
}

// ── ── SECTION 3: API KEYS ── ──

function ApiKeysSection() {
  const [keys, setKeys] = useState([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)
  const [newKey, setNewKey] = useState(null)
  const [keyName, setKeyName] = useState('')
  const [keyScopes, setKeyScopes] = useState(['leads:read', 'appointments:read'])
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    apiFetch('GET', '/integrations/api-keys').then(setKeys).catch(() => {}).finally(() => setLoading(false))
  }, [])

  async function create(e) {
    e.preventDefault()
    if (!keyName.trim()) return
    setCreating(true); setError('')
    try {
      const result = await apiFetch('POST', '/integrations/api-keys', { name: keyName.trim(), scopes: keyScopes })
      setNewKey(result.key); setKeys(prev => [result, ...prev])
      setKeyName(''); setKeyScopes(['leads:read', 'appointments:read']); setAdding(false)
    } catch (err) { setError(err.message) }
    finally { setCreating(false) }
  }

  async function revoke(id) {
    if (!window.confirm('Revoke this API key? Any integration using it will stop working.')) return
    await apiFetch('DELETE', `/integrations/api-keys/${id}`)
    setKeys(prev => prev.filter(k => k.id !== id))
  }

  return (
    <section className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <SectionHeader icon={Key} title="API Keys"
          description="Authenticate external tools and the MCP server with scoped bearer tokens." />
        {!adding && (
          <button onClick={() => setAdding(true)}
            className="flex items-center gap-1.5 text-sm font-semibold text-white bg-accent hover:bg-accent-dark px-4 py-2 rounded-lg transition-colors flex-shrink-0 mt-0.5">
            <Plus className="w-4 h-4" /> New Key
          </button>
        )}
      </div>

      {newKey && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-3">
          <p className="text-sm font-semibold text-amber-800">New API key — save it now</p>
          <p className="text-xs text-amber-700">This will <strong>not be shown again</strong>.</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-surface border border-amber-300 rounded-lg px-3 py-2 text-xs font-mono text-gray-800 break-all">{newKey}</code>
            <CopyButton text={newKey} className="text-amber-800 bg-amber-100 hover:bg-amber-200 border border-amber-300 flex-shrink-0" />
          </div>
          <button onClick={() => setNewKey(null)} className="text-xs font-semibold text-amber-700 hover:text-amber-900">Done →</button>
        </div>
      )}

      {adding && (
        <form onSubmit={create} className="bg-gray-50 border border-gray-200 rounded-xl p-5 space-y-4">
          <div>
            <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Key name</label>
            <input value={keyName} onChange={e => setKeyName(e.target.value)} required
              placeholder="e.g. HubSpot sync, Zapier, MCP agent"
              className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent" />
          </div>
          <div>
            <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-2">Permissions</label>
            <div className="space-y-2">
              {ALL_SCOPES.map(s => (
                <label key={s.id} className="flex items-center gap-2 cursor-pointer">
                  <input type="checkbox" checked={keyScopes.includes(s.id)}
                    onChange={() => setKeyScopes(prev => prev.includes(s.id) ? prev.filter(x => x !== s.id) : [...prev, s.id])}
                    className="w-4 h-4 rounded accent-accent" />
                  <span className="text-sm text-gray-700">{s.label}</span>
                  <code className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">{s.id}</code>
                </label>
              ))}
            </div>
          </div>
          {error && <p className="text-red-500 text-xs">{error}</p>}
          <div className="flex gap-2 pt-1">
            <button type="submit" disabled={creating}
              className="flex items-center gap-2 bg-accent text-white text-sm font-semibold px-4 py-2 rounded-lg hover:bg-accent-dark disabled:opacity-50 transition-colors">
              {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Key className="w-4 h-4" />}
              {creating ? 'Creating…' : 'Create Key'}
            </button>
            <button type="button" onClick={() => { setAdding(false); setError('') }}
              className="text-sm text-gray-500 hover:text-gray-700 px-3 py-2">Cancel</button>
          </div>
        </form>
      )}

      {loading
        ? <div className="flex justify-center py-6"><Loader2 className="w-5 h-5 animate-spin text-gray-400" /></div>
        : !keys.length && !adding ? (
          <div className="text-center py-10 border-2 border-dashed border-gray-200 rounded-xl">
            <Key className="w-8 h-8 text-gray-300 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-500">No API keys yet</p>
            <p className="text-xs text-gray-400 mt-1">Create a key to authenticate external tools and the MCP server.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {keys.map(k => (
              <div key={k.id} className="border border-gray-200 rounded-xl px-4 py-3 flex items-center gap-3">
                <Key className="w-4 h-4 text-gray-300 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800">{k.name}</p>
                  <div className="flex flex-wrap items-center gap-2 mt-0.5">
                    <code className="text-xs text-gray-400 font-mono">{k.key_prefix}••••</code>
                    {(k.scopes || []).map(s => (
                      <span key={s} className="text-xs bg-purple-50 text-purple-700 border border-purple-100 rounded-full px-1.5 py-0.5">{s}</span>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  {k.last_used && <span className="text-xs text-gray-400">Used {new Date(k.last_used).toLocaleDateString()}</span>}
                  <button onClick={() => revoke(k.id)} title="Revoke key"
                    className="text-red-400 hover:text-red-700 hover:bg-red-50 p-1.5 rounded-lg transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
    </section>
  )
}

// ── ── SECTION 4: MCP SERVER ── ──

function McpSection() {
  // Derived, not hardcoded: this string is copy-pasted by customers straight
  // into their MCP client config, so a stale literal here hands every one of
  // them a broken endpoint.
  const endpoint = `${BASE.replace(/\/$/, '')}/mcp/`

  const cliSnippet = `claude mcp add --transport http nexadesk "${endpoint}" --header "Authorization: Bearer YOUR_API_KEY"`

  const jsonSnippet = `{
  "mcpServers": {
    "nexadesk": {
      "type": "http",
      "url": "${endpoint}",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}`

  const tools = [
    { name: 'get_leads',        desc: 'List leads — filter by status or source' },
    { name: 'create_lead',      desc: 'Add a new lead (fires webhooks + CRM sync)' },
    { name: 'get_appointments', desc: 'Upcoming viewings with lead & property details' },
    { name: 'get_properties',   desc: 'Browse the property inventory' },
  ]

  return (
    <section className="space-y-4">
      <SectionHeader icon={Terminal} title="MCP Server"
        description="Give any AI agent direct access to NexaDesk — add leads, query data, check appointments." />

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {tools.map(t => (
          <div key={t.name} className="border border-gray-200 rounded-xl px-4 py-3 flex items-start gap-3">
            <Zap className="w-4 h-4 text-accent-ink mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-sm font-semibold text-gray-800 font-mono">{t.name}</p>
              <p className="text-xs text-gray-400 mt-0.5">{t.desc}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="border border-gray-200 rounded-xl p-4 space-y-2">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Endpoint</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono text-gray-800">{endpoint}</code>
          <CopyButton text={endpoint} className="text-gray-600 bg-gray-100 hover:bg-gray-200 border border-gray-200" />
        </div>
      </div>

      <div className="border border-gray-200 rounded-xl p-4 space-y-2">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Add via Claude Code CLI</p>
        <div className="flex items-start gap-2">
          <pre className="flex-1 bg-inverse text-green-400 rounded-lg px-3 py-2.5 text-xs font-mono overflow-x-auto whitespace-pre-wrap break-all">{cliSnippet}</pre>
          <CopyButton text={cliSnippet} className="text-gray-600 bg-gray-100 hover:bg-gray-200 border border-gray-200 flex-shrink-0" />
        </div>
      </div>

      <div className="border border-gray-200 rounded-xl p-4 space-y-2">
        <p className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Or add to .mcp.json</p>
        <div className="flex items-start gap-2">
          <pre className="flex-1 bg-inverse text-green-400 rounded-lg px-3 py-2.5 text-xs font-mono overflow-x-auto">{jsonSnippet}</pre>
          <CopyButton text={jsonSnippet} className="text-gray-600 bg-gray-100 hover:bg-gray-200 border border-gray-200 flex-shrink-0" />
        </div>
      </div>

      <p className="text-xs text-gray-400 px-1">
        Replace <code className="bg-gray-100 text-gray-600 px-1 rounded">YOUR_API_KEY</code> with a key from the API Keys section above.
        Scopes on the key control what the MCP agent can do.
      </p>
    </section>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Integrations() {
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-10">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Integrations</h1>
        <p className="text-gray-500 text-sm mt-1">Connect NexaDesk to your CRM, tools, and AI agents.</p>
      </div>
      <WebhooksSection />
      <CrmSection />
      <ApiKeysSection />
      <McpSection />
    </div>
  )
}
