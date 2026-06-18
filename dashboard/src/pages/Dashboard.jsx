import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Users, Phone, CalendarDays, TrendingUp, MessageSquare, Wrench, RefreshCw, ShoppingBag } from 'lucide-react'
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

export default function Dashboard() {
  const [stats, setStats] = useState(null)
  const [appointments, setAppointments] = useState([])
  const [recentLeads, setRecentLeads] = useState([])

  useEffect(() => {
    api.getAnalytics().then(setStats).catch(console.error)
    api.getAppointments().then(setAppointments).catch(console.error)
    api.getLeads({ limit: 20 }).then(data => {
      const arr = Array.isArray(data) ? data : (data.leads || data.items || [])
      setRecentLeads(arr.filter(l => l.conversations?.length > 0).slice(0, 6))
    }).catch(console.error)
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
