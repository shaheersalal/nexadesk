import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Eye, MousePointerClick, Users, ArrowDownWideNarrow, X, Globe } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

function StatCard({ icon: Icon, label, value, color = 'accent' }) {
  return (
    <div className="card flex items-start gap-4">
      <div className={`p-2.5 rounded-xl ${color === 'accent' ? 'bg-accent/10' : 'bg-blue-50'}`}>
        <Icon className={`w-5 h-5 ${color === 'accent' ? 'text-accent-ink' : 'text-blue-500'}`} />
      </div>
      <div>
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
}

function SiteBadge({ site }) {
  const label = site === 'shaheer_dev' ? 'shaheer.dev' : 'nexadesk.site'
  const color = site === 'shaheer_dev' ? 'bg-purple-50 text-purple-700' : 'bg-blue-50 text-blue-700'
  return <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>{label}</span>
}

function SessionDrawer({ sessionId, onClose }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setDetail(null)
    setError(null)
    api.getSiteSessionDetail(sessionId).then(setDetail).catch((e) => setError(e.message))
  }, [sessionId])

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <div className="w-full max-w-lg h-full bg-white overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">Session detail</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-700">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {!detail && !error && <p className="text-sm text-gray-400">Loading…</p>}

        {detail && (
          <>
            <div className="mb-6">
              <p className="text-xs text-gray-400 mb-1">Session ID</p>
              <p className="text-sm font-mono text-gray-700 break-all">{detail.session_id}</p>
            </div>

            <div className="mb-6">
              <p className="text-xs font-semibold text-gray-500 mb-2">Page events</p>
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {detail.events.map((e) => (
                  <div key={e.id} className="text-xs flex items-center gap-2 py-1 border-b border-gray-50">
                    <span className="text-gray-400 w-14 shrink-0">
                      {new Date(e.created_at).toLocaleTimeString()}
                    </span>
                    <span className="font-medium text-gray-700 w-20 shrink-0">{e.event_type}</span>
                    <span className="text-gray-500 truncate">
                      {e.path}
                      {e.event_type === 'scroll_depth' && e.event_data?.depth_pct != null && ` — ${e.event_data.depth_pct}%`}
                      {e.event_type === 'click' && e.event_data?.label && ` — ${e.event_data.label}`}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {detail.conversation ? (
              <div>
                <p className="text-xs font-semibold text-gray-500 mb-2">
                  Conversation ({detail.conversation.channel})
                </p>
                <div className="space-y-2">
                  {(detail.conversation.transcript || []).map((m, i) => (
                    <div
                      key={i}
                      className={`text-sm rounded-lg px-3 py-2 max-w-[85%] ${
                        m.role === 'user' ? 'bg-gray-100 text-gray-800' : 'bg-accent/10 text-gray-800 ml-auto'
                      }`}
                    >
                      {m.content}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-400">No chat or voice conversation on this session.</p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

export default function SiteAnalytics() {
  const [site, setSite] = useState('')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selectedSession, setSelectedSession] = useState(null)

  useEffect(() => {
    setData(null)
    setError(null)
    const params = site ? { site, days: 7 } : { days: 7 }
    api.getSiteAnalytics(params).then(setData).catch((e) => setError(e.message))
  }, [site])

  return (
    <div className="p-4 md:p-8">
      <div className="mb-6 md:mb-8 flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Site analytics</h1>
          <p className="text-gray-500 text-sm mt-1">
            shaheer.dev and nexadesk.site visitor activity — last 7 days
          </p>
        </div>
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {[
            { key: '', label: 'Both' },
            { key: 'shaheer_dev', label: 'shaheer.dev' },
            { key: 'nexadesk_site', label: 'nexadesk.site' },
          ].map((opt) => (
            <button
              key={opt.key}
              onClick={() => setSite(opt.key)}
              className={`text-xs font-medium px-3 py-1.5 rounded-md transition-colors ${
                site === opt.key ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Eye} label="Pageviews" value={data?.totals.pageviews ?? '—'} />
        <StatCard icon={Users} label="Unique sessions" value={data?.totals.unique_sessions ?? '—'} color="blue" />
        <StatCard icon={MousePointerClick} label="Clicks" value={data?.totals.clicks ?? '—'} color="blue" />
        <StatCard icon={ArrowDownWideNarrow} label="Scroll events" value={data?.totals.scroll_events ?? '—'} />
      </div>

      <div className="card overflow-x-auto">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Recent sessions</h2>
        {!data && !error && <p className="text-sm text-gray-400">Loading…</p>}
        {data && data.sessions.length === 0 && (
          <p className="text-sm text-gray-400">No visits recorded yet.</p>
        )}
        {data && data.sessions.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
                <th className="pb-2 pr-4 font-medium">Site</th>
                <th className="pb-2 pr-4 font-medium">IP</th>
                <th className="pb-2 pr-4 font-medium">Entry page</th>
                <th className="pb-2 pr-4 font-medium">Referrer</th>
                <th className="pb-2 pr-4 font-medium">Pageviews</th>
                <th className="pb-2 pr-4 font-medium">Clicks</th>
                <th className="pb-2 pr-4 font-medium">Talked?</th>
                <th className="pb-2 font-medium">Last seen</th>
              </tr>
            </thead>
            <tbody>
              {data.sessions.map((s) => (
                <tr
                  key={s.session_id}
                  onClick={() => setSelectedSession(s.session_id)}
                  className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer"
                >
                  <td className="py-2 pr-4"><SiteBadge site={s.site} /></td>
                  <td className="py-2 pr-4 font-mono text-xs text-gray-600">{s.ip_address || '—'}</td>
                  <td className="py-2 pr-4 text-gray-700 max-w-[160px] truncate">{s.first_path || '—'}</td>
                  <td className="py-2 pr-4 text-gray-500 max-w-[140px] truncate">
                    {s.referrer ? (
                      <span className="inline-flex items-center gap-1">
                        <Globe className="w-3 h-3 shrink-0" />
                        {s.referrer.replace(/^https?:\/\//, '')}
                      </span>
                    ) : 'direct'}
                  </td>
                  <td className="py-2 pr-4 text-gray-700">{s.pageviews}</td>
                  <td className="py-2 pr-4 text-gray-700">{s.clicks}</td>
                  <td className="py-2 pr-4">
                    {s.has_conversation ? (
                      <span className="text-xs font-medium text-green-700 bg-green-50 px-2 py-0.5 rounded-full">Yes</span>
                    ) : (
                      <span className="text-xs text-gray-400">—</span>
                    )}
                  </td>
                  <td className="py-2 text-gray-500 text-xs whitespace-nowrap">
                    {formatDistanceToNow(new Date(s.last_seen), { addSuffix: true })}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selectedSession && (
        <SessionDrawer sessionId={selectedSession} onClose={() => setSelectedSession(null)} />
      )}
    </div>
  )
}
