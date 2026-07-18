import { useState, useEffect } from 'react'
import { Plus, Trash2, Play, ChevronDown, ChevronUp, Check, X, Loader2, Copy, Plug } from 'lucide-react'
import { api } from '../lib/api'

const BASE = import.meta.env.VITE_API_URL || '/api'

const ALL_EVENTS = [
  { id: 'lead.created',       label: 'New Lead',            desc: 'Fired when a lead is captured via chat, voice, or manually' },
  { id: 'lead.status_changed',label: 'Lead Status Changed', desc: 'Fired when a lead moves through the pipeline' },
  { id: 'appointment.booked', label: 'Appointment Booked',  desc: 'Fired when a viewing is scheduled' },
  { id: 'call.ended',         label: 'Call Ended',          desc: 'Fired when an AI phone call finishes' },
]

async function authHeaders() {
  const { supabase } = await import('../lib/supabase')
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

async function apiFetch(method, path, body) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/integrations${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data.detail || 'Request failed')
  return data
}

// ── Event selector ────────────────────────────────────────────────────────────

function EventSelector({ selected, onChange }) {
  return (
    <div className="space-y-2">
      {ALL_EVENTS.map(ev => (
        <label key={ev.id} className="flex items-start gap-3 cursor-pointer group">
          <div className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${selected.includes(ev.id) ? 'bg-accent border-accent' : 'border-gray-300 group-hover:border-accent'}`}
            onClick={() => onChange(selected.includes(ev.id) ? selected.filter(e => e !== ev.id) : [...selected, ev.id])}>
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

// ── Add webhook form ──────────────────────────────────────────────────────────

function AddWebhookForm({ onCreated, onCancel }) {
  const [url, setUrl] = useState('')
  const [events, setEvents] = useState(['lead.created'])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [secret, setSecret] = useState(null)
  const [copied, setCopied] = useState(false)

  async function submit(e) {
    e.preventDefault()
    if (!url) return
    if (!events.length) { setError('Select at least one event.'); return }
    setLoading(true); setError('')
    try {
      const result = await apiFetch('POST', '/webhooks', { url, events })
      setSecret(result.secret)
      onCreated(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  function copySecret() {
    navigator.clipboard.writeText(secret)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (secret) {
    return (
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-5 space-y-3">
        <p className="text-sm font-semibold text-amber-800">Webhook created — save your secret key now</p>
        <p className="text-xs text-amber-700">Use this to verify NexaDesk requests on your server. It will <strong>not be shown again</strong>.</p>
        <div className="flex items-center gap-2">
          <code className="flex-1 bg-white border border-amber-300 rounded-lg px-3 py-2 text-xs font-mono text-gray-800 truncate">{secret}</code>
          <button onClick={copySecret} className="flex items-center gap-1.5 text-xs font-semibold text-amber-800 bg-amber-100 hover:bg-amber-200 border border-amber-300 px-3 py-2 rounded-lg transition-colors">
            {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
        <button onClick={onCancel} className="text-xs font-semibold text-amber-700 hover:text-amber-900">Done →</button>
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="bg-gray-50 border border-gray-200 rounded-xl p-5 space-y-4">
      <div>
        <label className="block text-xs font-semibold text-gray-600 uppercase tracking-wide mb-1.5">Endpoint URL</label>
        <input
          type="url" required value={url} onChange={e => setUrl(e.target.value)}
          placeholder="https://your-crm.com/webhooks/nexadesk"
          className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
        />
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
        <button type="button" onClick={onCancel} className="text-sm text-gray-500 hover:text-gray-700 px-3 py-2 transition-colors">Cancel</button>
      </div>
    </form>
  )
}

// ── Log drawer ────────────────────────────────────────────────────────────────

function LogDrawer({ webhookId, onClose }) {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiFetch('GET', `/webhooks/${webhookId}/logs`)
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

// ── Webhook row ───────────────────────────────────────────────────────────────

function WebhookRow({ webhook, onDelete }) {
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [logsOpen, setLogsOpen] = useState(false)
  const [deleting, setDeleting] = useState(false)

  async function test() {
    setTesting(true); setTestResult(null)
    try {
      await apiFetch('POST', `/webhooks/${webhook.id}/test`)
      setTestResult('sent')
    } catch {
      setTestResult('error')
    } finally {
      setTesting(false)
      setTimeout(() => setTestResult(null), 3000)
    }
  }

  async function del() {
    if (!window.confirm('Delete this webhook?')) return
    setDeleting(true)
    try {
      await apiFetch('DELETE', `/webhooks/${webhook.id}`)
      onDelete(webhook.id)
    } finally {
      setDeleting(false)
    }
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
              return (
                <span key={ev} className="text-xs bg-blue-50 text-blue-700 border border-blue-100 rounded-full px-2 py-0.5">
                  {found?.label || ev}
                </span>
              )
            })}
          </div>
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button onClick={test} disabled={testing}
            title="Send a test event"
            className="flex items-center gap-1 text-xs font-medium text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 px-2.5 py-1.5 rounded-lg transition-colors disabled:opacity-50">
            {testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            {testResult === 'sent' ? 'Sent ✓' : testResult === 'error' ? 'Error' : 'Test'}
          </button>
          <button onClick={() => setLogsOpen(o => !o)} title="View delivery log"
            className="text-xs font-medium text-gray-600 hover:text-gray-900 bg-gray-100 hover:bg-gray-200 px-2.5 py-1.5 rounded-lg transition-colors flex items-center gap-1">
            Logs {logsOpen ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </button>
          <button onClick={del} disabled={deleting} title="Delete webhook"
            className="text-red-400 hover:text-red-600 hover:bg-red-50 p-1.5 rounded-lg transition-colors disabled:opacity-50">
            {deleting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
          </button>
        </div>
      </div>
      {logsOpen && <LogDrawer webhookId={webhook.id} onClose={() => setLogsOpen(false)} />}
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Integrations() {
  const [webhooks, setWebhooks] = useState([])
  const [loading, setLoading] = useState(true)
  const [adding, setAdding] = useState(false)

  useEffect(() => {
    apiFetch('GET', '/webhooks')
      .then(setWebhooks).catch(() => {}).finally(() => setLoading(false))
  }, [])

  function onCreated(webhook) {
    setWebhooks(prev => [webhook, ...prev])
  }

  function onDelete(id) {
    setWebhooks(prev => prev.filter(w => w.id !== id))
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-8">

      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Integrations</h1>
        <p className="text-gray-500 text-sm mt-1">Connect NexaDesk to your CRM and other tools.</p>
      </div>

      {/* Webhooks section */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
              <Plug className="w-4 h-4 text-accent" /> Webhooks
            </h2>
            <p className="text-xs text-gray-400 mt-0.5">
              NexaDesk POSTs a JSON payload to your URL in real time when events occur.
              Verify requests using the <code className="bg-gray-100 px-1 rounded">X-NexaDesk-Signature</code> header.
            </p>
          </div>
          {!adding && (
            <button onClick={() => setAdding(true)}
              className="flex items-center gap-1.5 text-sm font-semibold text-white bg-accent hover:bg-accent-dark px-4 py-2 rounded-lg transition-colors">
              <Plus className="w-4 h-4" /> Add
            </button>
          )}
        </div>

        {adding && (
          <AddWebhookForm
            onCreated={(w) => { onCreated(w); }}
            onCancel={() => setAdding(false)}
          />
        )}

        {loading && (
          <div className="flex justify-center py-8">
            <Loader2 className="w-5 h-5 animate-spin text-gray-400" />
          </div>
        )}

        {!loading && !webhooks.length && !adding && (
          <div className="text-center py-10 border-2 border-dashed border-gray-200 rounded-xl">
            <Plug className="w-8 h-8 text-gray-300 mx-auto mb-3" />
            <p className="text-sm font-medium text-gray-500">No webhooks yet</p>
            <p className="text-xs text-gray-400 mt-1">Add your first endpoint to start receiving events.</p>
          </div>
        )}

        <div className="space-y-3">
          {webhooks.map(w => (
            <WebhookRow key={w.id} webhook={w} onDelete={onDelete} />
          ))}
        </div>
      </section>

      {/* Coming soon */}
      <section className="space-y-3">
        <h2 className="text-base font-semibold text-gray-900">One-Click CRM Connections</h2>
        <p className="text-xs text-gray-400">Connect directly — no copy-pasting, no code. Coming next.</p>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {['HubSpot', 'Zoho CRM', 'GoHighLevel', 'Pipedrive', 'Salesforce', 'Zapier'].map(name => (
            <div key={name} className="flex items-center gap-3 border border-gray-200 rounded-xl p-3.5 opacity-50 cursor-not-allowed select-none">
              <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-400">
                {name[0]}
              </div>
              <div>
                <p className="text-sm font-medium text-gray-700">{name}</p>
                <p className="text-xs text-gray-400">Coming soon</p>
              </div>
            </div>
          ))}
        </div>
      </section>

    </div>
  )
}
