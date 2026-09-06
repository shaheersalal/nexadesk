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

            {detail.live_fetches?.length > 0 && (
              <div className="mb-6">
                <p className="text-xs font-semibold text-gray-500 mb-2">Audition URL entered</p>
                {detail.live_fetches.map((lf, i) => (
                  <div key={i} className="mb-2 text-xs">
                    <a href={lf.url} target="_blank" rel="noreferrer" className="text-accent-ink font-medium break-all">
                      {lf.url}
                    </a>
                    {lf.phone && <span className="text-gray-400 ml-2">(call: {lf.phone})</span>}
                    {lf.scraped_excerpt && (
                      <pre className="mt-1 whitespace-pre-wrap bg-gray-50 rounded-lg p-2 max-h-32 overflow-y-auto text-gray-600">
                        {lf.scraped_excerpt.slice(0, 600)}
                      </pre>
                    )}
                  </div>
                ))}
              </div>
            )}

            {detail.reviews?.length > 0 && (
              <div className="mb-6">
                <p className="text-xs font-semibold text-gray-500 mb-2">Review / contact left</p>
                {detail.reviews.map((r, i) => (
                  <div key={i} className="text-xs mb-2 bg-yellow-50 rounded-lg p-2">
                    {r.stars && <span className="text-yellow-500">{'★'.repeat(r.stars)}{'☆'.repeat(5 - r.stars)}</span>}
                    {r.review_text && <p className="text-gray-700 mt-1">{r.review_text}</p>}
                    {r.email && <p className="text-gray-500 mt-1">{r.email}</p>}
                  </div>
                ))}
              </div>
            )}

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

function VisitorsTable({ site }) {
  const [visitors, setVisitors] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setVisitors(null)
    setError(null)
    const params = site ? { site } : {}
    api.getSiteVisitors(params).then((d) => setVisitors(d.visitors)).catch((e) => setError(e.message))
  }, [site])

  return (
    <div className="card overflow-x-auto">
      <h2 className="text-sm font-semibold text-gray-700 mb-1">Visitors by IP</h2>
      <p className="text-xs text-gray-400 mb-4">One row per IP - a returning visitor accumulates dates instead of duplicating.</p>
      {error && <p className="text-sm text-red-600">{error}</p>}
      {!visitors && !error && <p className="text-sm text-gray-400">Loading…</p>}
      {visitors && visitors.length === 0 && <p className="text-sm text-gray-400">No visitors recorded yet.</p>}
      {visitors && visitors.length > 0 && (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-gray-400 border-b border-gray-100">
              <th className="pb-2 pr-4 font-medium">Site</th>
              <th className="pb-2 pr-4 font-medium">IP</th>
              <th className="pb-2 pr-4 font-medium">Visits</th>
              <th className="pb-2 pr-4 font-medium">Dates seen</th>
              <th className="pb-2 pr-4 font-medium">Last URL entered</th>
              <th className="pb-2 pr-4 font-medium">Email</th>
              <th className="pb-2 pr-4 font-medium">Review</th>
              <th className="pb-2 font-medium">Last seen</th>
            </tr>
          </thead>
          <tbody>
            {visitors.map((v) => (
              <tr key={`${v.site}-${v.ip_address}`} className="border-b border-gray-50">
                <td className="py-2 pr-4"><SiteBadge site={v.site} /></td>
                <td className="py-2 pr-4 font-mono text-xs text-gray-600">{v.ip_address}</td>
                <td className="py-2 pr-4 text-gray-700">{v.session_count}</td>
                <td className="py-2 pr-4 text-gray-500 text-xs max-w-[220px] truncate" title={(v.visit_dates || []).join(', ')}>
                  {(v.visit_dates || []).join(', ')}
                </td>
                <td className="py-2 pr-4 text-gray-500 text-xs max-w-[160px] truncate">{v.last_entered_url || '—'}</td>
                <td className="py-2 pr-4 text-gray-500 text-xs">{v.email || '—'}</td>
                <td className="py-2 pr-4 text-gray-500 text-xs">
                  {v.last_review_stars ? '★'.repeat(v.last_review_stars) : '—'}
                </td>
                <td className="py-2 text-gray-500 text-xs whitespace-nowrap">
                  {formatDistanceToNow(new Date(v.last_seen), { addSuffix: true })}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

export default function SiteAnalytics() {
  const [site, setSite] = useState('')
  const [view, setView] = useState('sessions') // sessions | visitors
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

      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 mb-4 w-fit">
        {[
          { key: 'sessions', label: 'Recent sessions' },
          { key: 'visitors', label: 'Visitors by IP' },
        ].map((opt) => (
          <button
            key={opt.key}
            onClick={() => setView(opt.key)}
            className={`text-xs font-medium px-3 py-1.5 rounded-md transition-colors ${
              view === opt.key ? 'bg-white shadow-sm text-gray-900' : 'text-gray-500'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {view === 'visitors' && <VisitorsTable site={site} />}

      {view === 'sessions' && (
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
      )}

      {selectedSession && (
        <SessionDrawer sessionId={selectedSession} onClose={() => setSelectedSession(null)} />
      )}
    </div>
  )
}
