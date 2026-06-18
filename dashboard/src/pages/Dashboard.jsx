import { useEffect, useState, useRef } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { supabase } from '../lib/supabase'
import { Users, Phone, CalendarDays, TrendingUp, MessageSquare, Wrench, RefreshCw, ShoppingBag, Radio } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

function StatCard({ icon: Icon, label, value, sub, color = 'accent' }) {
  return (
    <div className="card flex items-start gap-4">
      <div className={`p-2.5 rounded-xl ${color === 'accent' ? 'bg-accent/10' : 'bg-blue-50'}`}>
        <Icon className={`w-5 h-5 ${color === 'accent' ? 'text-accent' : 'text-blue-500'}`} />
      </div>
      <div>
        <p className="text-2xl font-semibold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
        {sub && <p className="text-xs text-green-600 mt-0.5">{sub}</p>}
      </div>
    </div>
  )
}

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
  return `${Math.floor(diff / 3600)}h ago`
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
  const [stats, setStats] = useState(null)
  const [appointments, setAppointments] = useState([])
  const [recentLeads, setRecentLeads] = useState([])
  const [liveFeed, setLiveFeed] = useState([])
  const companyIdRef = useRef(null)

  async function loadRecentLeads() {
    const data = await api.getLeads({ limit: 20 })
    const arr = Array.isArray(data) ? data : (data.leads || data.items || [])
    setRecentLeads(arr.filter(l => l.conversations?.length > 0).slice(0, 6))
  }

  async function loadLiveFeed() {
    const cid = companyIdRef.current
    if (!cid) return
    const { data } = await supabase
      .from('conversations')
      .select('id, channel, started_at, lead_id, leads(name)')
      .eq('company_id', cid)
      .order('started_at', { ascending: false })
      .limit(8)
    if (data) {
      setLiveFeed(data.map(c => ({
        ...c,
        lead_name: c.leads?.name || null,
        fresh: false,
      })))
    }
  }

  useEffect(() => {
    api.getAnalytics().then(setStats).catch(console.error)
    api.getAppointments().then(setAppointments).catch(console.error)
    loadRecentLeads().catch(console.error)

    // Get company_id once, then load feed + subscribe to realtime
    supabase.from('users')
      .select('company_id')
      .then(async ({ data }) => {
        const { data: { user } } = await supabase.auth.getUser()
        if (!user) return
        const row = data?.find(r => r)
        // Fetch company_id via auth user
        const { data: uRow } = await supabase.from('users').select('company_id').eq('id', user.id).single()
        if (!uRow?.company_id) return
        companyIdRef.current = uRow.company_id
        await loadLiveFeed()

        const channel = supabase
          .channel('live_conv_feed')
          .on(
            'postgres_changes',
            { event: 'INSERT', schema: 'public', table: 'conversations', filter: `company_id=eq.${uRow.company_id}` },
            async (payload) => {
              const c = payload.new
              // Fetch lead name
              let lead_name = null
              if (c.lead_id) {
                const { data: lead } = await supabase.from('leads').select('name').eq('id', c.lead_id).single()
                lead_name = lead?.name || null
              }
              setLiveFeed(prev => [{ ...c, lead_name, fresh: true }, ...prev.slice(0, 7)])
              // Also refresh the recent AI-handled requests list
              loadRecentLeads().catch(console.error)
            }
          )
          .subscribe()

        return () => supabase.removeChannel(channel)
      })
      .catch(console.error)
  }, [])

  const statusChartData = stats
    ? Object.entries(stats.leads_by_status).map(([name, count]) => ({ name, count }))
    : []

  const sourceChartData = stats
    ? Object.entries(stats.leads_by_source).map(([name, count]) => ({ name, count }))
    : []

  return (
    <div className="p-4 md:p-8">
      <div className="mb-6 md:mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">Your AI receptionist at a glance</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Users}        label="Total leads"         value={stats?.total_leads ?? '—'}             sub={`+${stats?.leads_today ?? 0} today`} />
        <StatCard icon={TrendingUp}   label="Avg lead score"      value={stats?.avg_score ?? '—'}               color="blue" />
        <StatCard icon={CalendarDays} label="Upcoming appts"      value={stats?.appointments_upcoming ?? '—'}   color="blue" />
        <StatCard icon={MessageSquare} label="Total conversations" value={stats?.total_conversations ?? '—'}    />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Leads by Status</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={statusChartData} barSize={24}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#e8a87c" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="card">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Leads by Source</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={sourceChartData} barSize={24}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="count" fill="#1a1a2e" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
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
          <p className="text-sm text-gray-400 text-center py-6">No recent conversations</p>
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
          <p className="text-sm text-gray-400 text-center py-8">No upcoming appointments</p>
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
