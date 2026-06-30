import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { Users, TrendingUp, CalendarDays, MessageSquare } from 'lucide-react'
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

export default function Analytics() {
  const [stats, setStats] = useState(null)

  useEffect(() => {
    api.getAnalytics().then(setStats).catch(console.error)
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
        <h1 className="text-2xl font-semibold text-gray-900">Analytics</h1>
        <p className="text-gray-500 text-sm mt-1">Lead volume and pipeline breakdown</p>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard icon={Users}        label="Total leads"         value={stats?.total_leads ?? '—'}             sub={`+${stats?.leads_today ?? 0} today`} />
        <StatCard icon={TrendingUp}   label="Avg lead score"      value={stats?.avg_score ?? '—'}               color="blue" />
        <StatCard icon={CalendarDays} label="Upcoming appts"      value={stats?.appointments_upcoming ?? '—'}   color="blue" />
        <StatCard icon={MessageSquare} label="Total conversations" value={stats?.total_conversations ?? '—'}    />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
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
    </div>
  )
}
