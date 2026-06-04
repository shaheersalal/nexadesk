import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { CalendarDays, Plus, X, Clock } from 'lucide-react'
import { format, isToday, isTomorrow } from 'date-fns'

function dateLabel(dt) {
  if (isToday(new Date(dt))) return 'Today'
  if (isTomorrow(new Date(dt))) return 'Tomorrow'
  return format(new Date(dt), 'EEE, MMM d')
}

const STATUS_COLORS = {
  scheduled:  'bg-blue-50 text-blue-700',
  confirmed:  'bg-green-50 text-green-700',
  completed:  'bg-gray-100 text-gray-500',
  cancelled:  'bg-red-50 text-red-500',
  no_show:    'bg-orange-50 text-orange-600',
}

export default function Appointments() {
  const [appointments, setAppointments] = useState([])
  const [showForm, setShowForm] = useState(false)
  const [leads, setLeads] = useState([])
  const [properties, setProperties] = useState([])
  const [form, setForm] = useState({ lead_id: '', property_id: '', datetime: '', duration_minutes: 30, type: 'showing', notes: '' })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.getAppointments().then(setAppointments).catch(console.error)
    api.getLeads().then(setLeads).catch(console.error)
    api.getProperties().then(setProperties).catch(console.error)
  }, [])

  async function handleCreate(e) {
    e.preventDefault()
    setSaving(true)
    const data = { ...form, duration_minutes: parseInt(form.duration_minutes) }
    const saved = await api.createAppointment(data)
    setAppointments((prev) => [saved, ...prev])
    setShowForm(false)
    setSaving(false)
  }

  async function handleStatusChange(id, status) {
    await api.updateAppointment(id, { status })
    setAppointments((prev) => prev.map((a) => a.id === id ? { ...a, status } : a))
  }

  async function handleDelete(id) {
    if (!confirm('Cancel this appointment?')) return
    await api.deleteAppointment(id)
    setAppointments((prev) => prev.filter((a) => a.id !== id))
  }

  return (
    <div className="p-8 max-w-3xl">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Appointments</h1>
          <p className="text-gray-500 text-sm mt-1">{appointments.length} upcoming</p>
        </div>
        <button onClick={() => setShowForm(true)} className="btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />Schedule
        </button>
      </div>

      {/* Form modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <h2 className="text-lg font-semibold">Schedule Appointment</h2>
              <button onClick={() => setShowForm(false)}><X className="w-5 h-5 text-gray-400" /></button>
            </div>
            <form onSubmit={handleCreate} className="p-6 space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Lead *</label>
                <select
                  required
                  value={form.lead_id}
                  onChange={(e) => setForm({ ...form, lead_id: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  <option value="">Select lead…</option>
                  {leads.map((l) => <option key={l.id} value={l.id}>{l.name || l.phone || l.email || 'Unknown'}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Property</label>
                <select
                  value={form.property_id}
                  onChange={(e) => setForm({ ...form, property_id: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  <option value="">No specific property</option>
                  {properties.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Date & Time *</label>
                  <input
                    type="datetime-local"
                    required
                    value={form.datetime}
                    onChange={(e) => setForm({ ...form, datetime: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">Duration (min)</label>
                  <input
                    type="number"
                    value={form.duration_minutes}
                    onChange={(e) => setForm({ ...form, duration_minutes: e.target.value })}
                    className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Type</label>
                <select
                  value={form.type}
                  onChange={(e) => setForm({ ...form, type: e.target.value })}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                >
                  {['showing', 'call', 'meeting', 'open_house'].map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Notes</label>
                <textarea
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  rows={2}
                  className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
                <button type="submit" disabled={saving} className="btn-primary">
                  {saving ? 'Scheduling…' : 'Schedule'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Appointment list */}
      {appointments.length === 0 ? (
        <div className="card text-center py-16">
          <CalendarDays className="w-10 h-10 text-gray-200 mx-auto mb-4" />
          <p className="text-gray-500 font-medium">No appointments scheduled</p>
        </div>
      ) : (
        <div className="space-y-3">
          {appointments.map((appt) => (
            <div key={appt.id} className="card flex items-start gap-4">
              <div className="text-center flex-shrink-0 w-16">
                <p className="text-xs font-semibold text-accent">{dateLabel(appt.datetime)}</p>
                <p className="text-lg font-bold text-gray-900">
                  {format(new Date(appt.datetime), 'h:mm')}
                </p>
                <p className="text-xs text-gray-400">{format(new Date(appt.datetime), 'a')}</p>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <p className="font-medium text-gray-900 text-sm">{appt.leads?.name || 'Unknown lead'}</p>
                  <span className={`status-pill ${STATUS_COLORS[appt.status] || ''}`}>{appt.status}</span>
                </div>
                {appt.properties?.title && (
                  <p className="text-xs text-gray-400">{appt.properties.title}</p>
                )}
                <div className="flex items-center gap-1 text-xs text-gray-400 mt-1">
                  <Clock className="w-3 h-3" />{appt.duration_minutes} min · {appt.type.replace('_', ' ')}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={appt.status}
                  onChange={(e) => handleStatusChange(appt.id, e.target.value)}
                  className="text-xs border border-gray-100 rounded-md px-2 py-1 text-gray-500"
                >
                  {Object.keys(STATUS_COLORS).map((s) => (
                    <option key={s} value={s}>{s.replace('_', ' ')}</option>
                  ))}
                </select>
                <button onClick={() => handleDelete(appt.id)} className="text-gray-300 hover:text-red-400">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
