import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { api, getCompanyId } from '../lib/api'
import { supabase } from '../lib/supabase'
import { Phone, CalendarDays, MessageSquare, Wrench, RefreshCw, ShoppingBag, Radio, Flame, CheckCircle2 } from 'lucide-react'
import ScoreBadge from '../components/ScoreBadge'
import EmptyState from '../components/EmptyState'

function reqIcon(notes) {
  if (!notes) return { icon: MessageSquare, color: 'text-gray-400 bg-gray-50', label: 'Inquiry' }
  if (notes.startsWith('[MAINTENANCE]')) return { icon: Wrench, color: 'text-orange-500 bg-orange-50', label: 'Maintenance' }
  if (notes.startsWith('[LEASE RENEWAL]')) return { icon: RefreshCw, color: 'text-purple-500 bg-purple-50', label: 'Lease Renewal' }
  return { icon: ShoppingBag, color: 'text-accent bg-accent/10', label: 'Buyer Inquiry' }
}

function timeAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso)) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`
  return `${Math.floor(diff / 86400)}d ago`
}

function isToday(iso) {
  const d = new Date(iso)
  const now = new Date()
  return d.getFullYear() === now.getFullYear() && d.getMonth() === now.getMonth() && d.getDate() === now.getDate()
}

function LiveFeedItem({ item }) {
  const isVoice = item.channel === 'voice'
  return (
    <Link
      to={item.lead_id ? `/dashboard/leads/${item.lead_id}` : '#'}
      className="flex items-center gap-3 py-2.5 border-b border-gray-50 last:border-0 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors group"
    >
      <div className={`w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 ${
        isVoice ? 'bg-green-50 text-green-600' : 'bg-blue-50 text-blue-500'
      }`}>
        {isVoice ? <Phone className="w-3.5 h-3.5" /> : <MessageSquare className="w-3.5 h-3.5" />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate group-hover:text-accent">
          {item.lead_name || (isVoice ? 'Incoming call' : 'New chat')}
        </p>
        <p className="text-xs text-gray-400 capitalize">{item.channel}</p>
      </div>
      <div className="text-right flex-shrink-0">
        <span className={`inline-block w-2 h-2 rounded-full mb-1 ${item.fresh ? 'bg-green-400 animate-pulse' : 'bg-gray-200'}`} />
        <p className="text-xs text-gray-400">{timeAgo(item.started_at)}</p>
      </div>
    </Link>
  )
}

export default function Dashboard() {
  const [appointments, setAppointments] = useState([])
  const [recentLeads, setRecentLeads] = useState([])
  const [hotLeads, setHotLeads] = useState([])
  const [liveFeed, setLiveFeed] = useState([])
  const [last24h, setLast24h] = useState([])
  const companyIdRef = useRef(null)

  async function loadLeads() {
    const data = await api.getLeads({ limit: 50 })
    const arr = Array.isArray(data) ? data : (data.leads || data.items || [])
    setRecentLeads(arr.filter(l => l.conversations?.length > 0).slice(0, 6))
    setHotLeads(arr.filter(l => (l.score || 0) >= 70 && l.status === 'new').slice(0, 5))
  }

  async function loadLiveFeed() {
    if (!companyIdRef.current) return
    // No company_id filter — RLS (accessible_company_ids()) returns rows from
    // all accessible companies for parent accounts, own-company only for others.
    // The realtime subscription below is still scoped to own company_id only
    // (acceptable Phase 6 limitation; multi-company realtime would need N subscriptions).
    const { data } = await supabase
      .from('conversations')
      .select('id, channel, started_at, lead_id, leads(name)')
      .order('started_at', { ascending: false })
      .limit(8)
    if (data) {
      setLiveFeed(data.map(c => ({
        ...c,
        lead_name: c.leads?.name || null,
        fresh: false,
      })))
    }

    const since = new Date(Date.now() - 24 * 3600 * 1000).toISOString()
    const { data: recent } = await supabase
      .from('conversations')
      .select('id, channel, started_at, lead_id, leads(name)')
      .gte('started_at', since)
      .order('started_at', { ascending: false })
    if (recent) setLast24h(recent.map(c => ({ ...c, lead_name: c.leads?.name || null })))
  }

  useEffect(() => {
    let realtimeChannel = null

    Promise.all([
      api.getAppointments().then(setAppointments),
      loadLeads(),
    ]).catch(console.error)

    ;(async () => {
      try {
        const cid = await getCompanyId()
        if (!cid) return
        companyIdRef.current = cid
        await loadLiveFeed()

        realtimeChannel = supabase
          .channel('live_conv_feed')
          .on(
            'postgres_changes',
            { event: 'INSERT', schema: 'public', table: 'conversations', filter: `company_id=eq.${cid}` },
            async (payload) => {
              const c = payload.new
              let lead_name = null
              if (c.lead_id) {
                const { data: lead } = await supabase.from('leads').select('name').eq('id', c.lead_id).single()
                lead_name = lead?.name || null
              }
              setLiveFeed(prev => [{ ...c, lead_name, fresh: true }, ...prev.slice(0, 7)])
              setLast24h(prev => [{ ...c, lead_name }, ...prev])
              loadLeads().catch(console.error)
            }
          )
          .subscribe()
      } catch (e) {
        console.error('Live feed setup error:', e)
      }
    })()

    return () => {
      if (realtimeChannel) supabase.removeChannel(realtimeChannel)
    }
  }, [])

  const todaysAppointments = appointments.filter(a => isToday(a.datetime))
  const callsToday = last24h.filter(c => c.channel === 'voice').length
  const chatsToday = last24h.filter(c => c.channel !== 'voice').length

  return (
    <div className="p-4 md:p-8">
      <div className="mb-6 md:mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">What needs your attention today</p>
      </div>

      {/* Today's Actions */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-8">
        {/* Hot leads to contact */}
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Flame className="w-4 h-4 text-red-500" />
            Hot Leads to Contact
          </h2>
          {hotLeads.length === 0 ? (
            <EmptyState
              icon={CheckCircle2}
              title="All caught up"
              hint="No hot leads waiting on a first contact right now."
            />
          ) : (
            <div className="space-y-1">
              {hotLeads.map(lead => (
                <Link
                  key={lead.id}
                  to={`/dashboard/leads/${lead.id}`}
                  className="flex items-center justify-between gap-2 py-2 border-b border-gray-50 last:border-0 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors group"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate group-hover:text-accent">{lead.name || 'Unknown'}</p>
                    <p className="text-xs text-gray-400">{timeAgo(lead.created_at)}</p>
                  </div>
                  <ScoreBadge score={lead.score} />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Last 24h activity */}
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <Radio className="w-4 h-4 text-green-500" />
            Last 24h Activity
          </h2>
          <div className="flex items-center gap-4 mb-3">
            <div className="flex items-center gap-2 text-sm">
              <Phone className="w-3.5 h-3.5 text-green-600" />
              <span className="font-semibold text-gray-900">{callsToday}</span>
              <span className="text-gray-400">calls</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <MessageSquare className="w-3.5 h-3.5 text-blue-500" />
              <span className="font-semibold text-gray-900">{chatsToday}</span>
              <span className="text-gray-400">chats</span>
            </div>
          </div>
          {last24h.length === 0 ? (
            <EmptyState
              icon={Radio}
              title="No activity yet"
              hint="Calls and chats from the last 24 hours will show up here."
            />
          ) : (
            <div className="space-y-1">
              {last24h.slice(0, 5).map(item => (
                <LiveFeedItem key={item.id} item={item} />
              ))}
            </div>
          )}
        </div>

        {/* Today's appointments */}
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
            <CalendarDays className="w-4 h-4 text-accent" />
            Today's Appointments
          </h2>
          {todaysAppointments.length === 0 ? (
            <EmptyState
              icon={CalendarDays}
              title="Nothing scheduled today"
              hint="Appointments booked for today will show up here."
              actionLabel="View all appointments"
              actionTo="/dashboard/appointments"
            />
          ) : (
            <div className="space-y-1">
              {todaysAppointments.map(appt => (
                <Link
                  key={appt.id}
                  to={appt.lead_id ? `/dashboard/leads/${appt.lead_id}` : '/dashboard/appointments'}
                  className="flex items-center justify-between gap-2 py-2 border-b border-gray-50 last:border-0 hover:bg-gray-50 -mx-2 px-2 rounded-lg transition-colors group"
                >
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate group-hover:text-accent">{appt.leads?.name || 'Unknown lead'}</p>
                    <p className="text-xs text-gray-400">{appt.properties?.title || appt.type}</p>
                  </div>
                  <p className="text-xs font-medium text-gray-700 flex-shrink-0">
                    {new Date(appt.datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Recent AI-Handled Requests */}
      {recentLeads.length > 0 && (
        <div className="card mb-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-gray-700">Recent AI-Handled Requests</h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {recentLeads.map(lead => {
              const { icon: Icon, color, label } = reqIcon(lead.notes)
              const conv = lead.conversations?.[0]
              return (
                <Link key={lead.id} to={`/dashboard/leads/${lead.id}`}
                  className="flex items-start gap-3 p-3 rounded-lg border border-gray-100 hover:border-accent/40 hover:bg-gray-50 transition-colors group">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${color}`}>
                    <Icon className="w-4 h-4" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-gray-800 truncate group-hover:text-accent">{lead.name}</p>
                    <p className="text-xs text-gray-400">{label} · {conv?.channel || 'voice'}</p>
                    {lead.notes && (
                      <p className="text-xs text-gray-400 truncate mt-0.5">
                        {lead.notes.replace(/^\[.*?\]\s*/, '').slice(0, 60)}…
                      </p>
                    )}
                  </div>
                </Link>
              )
            })}
          </div>
        </div>
      )}

      {/* Live call feed */}
      <div className="card mb-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700 flex items-center gap-2">
            <Radio className="w-4 h-4 text-green-500" />
            Live Activity
          </h2>
          <span className="text-xs text-gray-400">last 8 sessions</span>
        </div>
        {liveFeed.length === 0 ? (
          <EmptyState
            icon={Radio}
            title="No recent conversations"
            hint="Calls and chats handled by your AI receptionist will appear here in real time."
          />
        ) : (
          <div>
            {liveFeed.map((item) => (
              <LiveFeedItem key={item.id} item={item} />
            ))}
          </div>
        )}
      </div>

      {/* Upcoming appointments */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">Upcoming Appointments</h2>
        </div>
        {appointments.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title="No upcoming appointments"
            hint="Appointments your AI books with clients will show up here."
            actionLabel="View all appointments"
            actionTo="/dashboard/appointments"
          />
        ) : (
          <div className="space-y-3">
            {appointments.slice(0, 5).map((appt) => (
              <div key={appt.id} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
                <div>
                  <p className="text-sm font-medium text-gray-800">{appt.leads?.name || 'Unknown lead'}</p>
                  <p className="text-xs text-gray-400">{appt.properties?.title || appt.type}</p>
                </div>
                <div className="text-right">
                  <p className="text-xs font-medium text-gray-700">
                    {new Date(appt.datetime).toLocaleDateString()}
                  </p>
                  <p className="text-xs text-gray-400">
                    {new Date(appt.datetime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
