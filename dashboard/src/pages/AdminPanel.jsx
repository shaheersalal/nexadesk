import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Phone, Mail, Building2, Globe, PhoneCall, Clock, RefreshCw, Send, CheckCircle, X } from 'lucide-react'
import { api } from '../lib/api'

const STATUS_STYLES = {
  pending:  { bg: 'bg-yellow-50', text: 'text-yellow-700', dot: 'bg-yellow-400', label: 'Pending' },
  invited:  { bg: 'bg-blue-50',   text: 'text-blue-700',   dot: 'bg-blue-400',   label: 'Invited' },
  active:   { bg: 'bg-green-50',  text: 'text-green-700',  dot: 'bg-green-500',  label: 'Active' },
}

function StatusPill({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.pending
  return (
    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${s.bg} ${s.text}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${s.dot}`} />
      {s.label}
    </span>
  )
}

function timeAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

export default function AdminPanel() {
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [inviting, setInviting] = useState(null)
  const [toast, setToast] = useState(null)

  async function load() {
    setLoading(true)
    try {
      const data = await api.getAdminRequests()
      setRequests(data)
    } catch (e) {
      showToast('Failed to load requests: ' + e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  function showToast(msg, type = 'success') {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  async function invite(req) {
    setInviting(req.id)
    try {
      await api.inviteUser({ request_id: req.id, email: req.email, name: req.name })
      setRequests(prev => prev.map(r => r.id === req.id ? { ...r, status: 'invited' } : r))
      showToast(`Invite sent to ${req.email}`)
    } catch (e) {
      showToast('Invite failed: ' + e.message, 'error')
    } finally {
      setInviting(null)
    }
  }

  const pending = requests.filter(r => r.status === 'pending')
  const rest = requests.filter(r => r.status !== 'pending')

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg text-sm font-medium transition-all
          ${toast.type === 'error' ? 'bg-red-600 text-white' : 'bg-green-600 text-white'}`}>
          {toast.type === 'error' ? <X className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
          {toast.msg}
        </div>
      )}

      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-navy-600 rounded-lg flex items-center justify-center">
            <Phone className="w-4 h-4 text-accent" />
          </div>
          <div>
            <span className="font-semibold text-gray-900">NexaDesk</span>
            <span className="text-gray-400 text-sm ml-2">· Admin Panel</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={load} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-900 transition-colors">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <Link to="/dashboard" className="text-sm text-gray-500 hover:text-gray-900 transition-colors">← Dashboard</Link>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Summary */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          {[
            { label: 'Total Requests', value: requests.length, icon: Building2, color: 'text-gray-600' },
            { label: 'Pending',        value: requests.filter(r => r.status === 'pending').length,  icon: Clock,       color: 'text-yellow-600' },
            { label: 'Invited',        value: requests.filter(r => r.status === 'invited').length,  icon: Send,        color: 'text-blue-600' },
          ].map(c => (
            <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4">
              <div className={`w-10 h-10 rounded-xl bg-gray-50 flex items-center justify-center ${c.color}`}>
                <c.icon className="w-5 h-5" />
              </div>
              <div>
                <p className="text-2xl font-bold text-gray-900">{c.value}</p>
                <p className="text-xs text-gray-500">{c.label}</p>
              </div>
            </div>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : requests.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-16 text-center">
            <p className="text-gray-400 text-sm">No access requests yet.</p>
          </div>
        ) : (
          <>
            {/* Pending — action needed */}
            {pending.length > 0 && (
              <div className="mb-6">
                <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Action Needed ({pending.length})</h2>
                <div className="flex flex-col gap-3">
                  {pending.map(req => <RequestRow key={req.id} req={req} onInvite={invite} inviting={inviting} />)}
                </div>
              </div>
            )}
            {/* Rest */}
            {rest.length > 0 && (
              <div>
                <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Past Requests</h2>
                <div className="flex flex-col gap-3">
                  {rest.map(req => <RequestRow key={req.id} req={req} onInvite={invite} inviting={inviting} />)}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function RequestRow({ req, onInvite, inviting }) {
  const isInviting = inviting === req.id

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-9 h-9 rounded-full bg-navy-600 flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
              {req.name?.[0]?.toUpperCase() || '?'}
            </div>
            <div>
              <p className="font-semibold text-gray-900">{req.name}</p>
              <p className="text-xs text-gray-400">{req.agency_name}</p>
            </div>
            <StatusPill status={req.status} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-x-6 gap-y-2 text-sm text-gray-600">
            <div className="flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <a href={`mailto:${req.email}`} className="text-blue-600 hover:underline truncate text-xs">{req.email}</a>
            </div>
            <div className="flex items-center gap-1.5">
              <Phone className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <a href={`tel:${req.phone}`} className="text-xs hover:underline">{req.phone}</a>
            </div>
            <div className="flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <span className="text-xs">{req.country || '—'}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <PhoneCall className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
              <span className="text-xs">{req.monthly_calls ? `${req.monthly_calls} calls/mo` : '—'}</span>
            </div>
          </div>

          <p className="text-[11px] text-gray-400 mt-3">{timeAgo(req.created_at)}</p>
        </div>

        {req.status === 'pending' && (
          <button
            onClick={() => onInvite(req)}
            disabled={isInviting}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold transition-all flex-shrink-0"
            style={{
              background: isInviting ? '#94a3b8' : '#1e3a5f',
              color: 'white',
              cursor: isInviting ? 'not-allowed' : 'pointer',
            }}
          >
            {isInviting ? (
              <><div className="w-3.5 h-3.5 border border-white border-t-transparent rounded-full animate-spin" /> Sending…</>
            ) : (
              <><Send className="w-3.5 h-3.5" /> Invite</>
            )}
          </button>
        )}
      </div>
    </div>
  )
}
