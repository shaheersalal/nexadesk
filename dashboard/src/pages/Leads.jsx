import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import { Plus, Phone, MessageSquare, Search } from 'lucide-react'
import ScoreBadge from '../components/ScoreBadge'

const COLUMNS = [
  { key: 'new',         label: 'New',         color: 'bg-gray-100 text-gray-700' },
  { key: 'contacted',   label: 'Contacted',   color: 'bg-blue-50 text-blue-700' },
  { key: 'qualified',   label: 'Qualified',   color: 'bg-yellow-50 text-yellow-700' },
  { key: 'appointment', label: 'Appointment', color: 'bg-purple-50 text-purple-700' },
  { key: 'closed_won',  label: 'Won',         color: 'bg-green-50 text-green-700' },
  { key: 'closed_lost', label: 'Lost',        color: 'bg-red-50 text-red-700' },
]

function LeadCard({ lead, onStatusChange }) {
  const sourceIcon = lead.source === 'voice'
    ? <Phone className="w-3 h-3" />
    : <MessageSquare className="w-3 h-3" />

  return (
    <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-2">
        <Link to={`/dashboard/leads/${lead.id}`} className="font-medium text-gray-900 text-sm hover:text-accent">
          {lead.name || 'Unknown'}
        </Link>
        <span className="flex items-center gap-1 text-xs text-gray-400">{sourceIcon}{lead.source}</span>
      </div>
      {lead.phone && <p className="text-xs text-gray-400 mb-1">{lead.phone}</p>}
      {lead.email && <p className="text-xs text-gray-400 mb-2 truncate">{lead.email}</p>}

      <div className="flex items-center justify-between">
        <ScoreBadge score={lead.score} />
        <select
          value={lead.status}
          onChange={(e) => onStatusChange(lead.id, e.target.value)}
          className="text-xs border border-gray-100 rounded-md px-1.5 py-0.5 text-gray-500 bg-white focus:outline-none"
          onClick={(e) => e.stopPropagation()}
        >
          {COLUMNS.map((c) => (
            <option key={c.key} value={c.key}>{c.label}</option>
          ))}
        </select>
      </div>
    </div>
  )
}

export default function Leads() {
  const [leads, setLeads] = useState([])
  const [search, setSearch] = useState('')

  useEffect(() => {
    api.getLeads().then(setLeads).catch(console.error)
  }, [])

  async function handleStatusChange(id, status) {
    await api.updateLeadStatus(id, status)
    setLeads((prev) => prev.map((l) => l.id === id ? { ...l, status } : l))
  }

  const filtered = leads.filter((l) =>
    !search || [l.name, l.phone, l.email].some((v) => v?.toLowerCase().includes(search.toLowerCase()))
  )

  const byStatus = COLUMNS.reduce((acc, col) => {
    acc[col.key] = filtered.filter((l) => l.status === col.key)
    return acc
  }, {})

  return (
    <div className="p-4 md:p-8">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Leads</h1>
          <p className="text-gray-500 text-sm mt-1">{leads.length} total leads</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search leads…"
              className="pl-9 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
        </div>
      </div>

      {/* Kanban board */}
      <div className="flex gap-4 overflow-x-auto pb-4">
        {COLUMNS.map((col) => (
          <div key={col.key} className="flex-shrink-0 w-64">
            <div className="flex items-center gap-2 mb-3">
              <span className={`status-pill ${col.color}`}>{col.label}</span>
              <span className="text-xs text-gray-400">{byStatus[col.key]?.length || 0}</span>
            </div>
            <div className="space-y-2">
              {(byStatus[col.key] || []).map((lead) => (
                <LeadCard key={lead.id} lead={lead} onStatusChange={handleStatusChange} />
              ))}
              {(byStatus[col.key] || []).length === 0 && (
                <div className="bg-gray-50 rounded-xl border-2 border-dashed border-gray-200 p-6 text-center">
                  <p className="text-xs text-gray-400">No leads</p>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
