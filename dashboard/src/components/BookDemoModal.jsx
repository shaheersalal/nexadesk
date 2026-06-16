import { useState } from 'react'
import { X, CheckCircle } from 'lucide-react'

const API = 'https://shaheersalal-nexadesk.hf.space'

export default function BookDemoModal({ open, onClose }) {
  const [form, setForm] = useState({ name: '', email: '', agency: '', phone: '' })
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  if (!open) return null

  function set(field) {
    return (e) => setForm((f) => ({ ...f, [field]: e.target.value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (!form.name || !form.email || !form.agency || !form.phone) return
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API}/book-demo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) throw new Error('Request failed')
      setDone(true)
    } catch {
      setError('Something went wrong. Email us directly at shaheersalal@gmail.com')
    } finally {
      setLoading(false)
    }
  }

  function handleClose() {
    setForm({ name: '', email: '', agency: '', phone: '' })
    setDone(false)
    setError('')
    onClose()
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      onClick={(e) => { if (e.target === e.currentTarget) handleClose() }}
    >
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 relative">
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 text-gray-300 hover:text-gray-500 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>

        {done ? (
          <div className="text-center py-6">
            <CheckCircle className="w-12 h-12 text-green-500 mx-auto mb-4" />
            <h3 className="text-xl font-bold text-gray-900 mb-2">You're on the list</h3>
            <p className="text-gray-500 text-sm leading-relaxed">
              Shaheer will reach out within 24 hours to schedule your personal setup call and get your AI receptionist live.
            </p>
            <button onClick={handleClose} className="mt-6 text-sm text-accent font-medium hover:underline">
              Close
            </button>
          </div>
        ) : (
          <>
            <div className="mb-6">
              <h2 className="text-xl font-bold text-gray-900">Book a Demo</h2>
              <p className="text-sm text-gray-500 mt-1">
                We'll personally set up your AI receptionist — phone number, knowledge base, everything. You just show up.
              </p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Full Name</label>
                <input
                  required
                  value={form.name}
                  onChange={set('name')}
                  placeholder="Ahmed Al-Rashid"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Email</label>
                <input
                  required
                  type="email"
                  value={form.email}
                  onChange={set('email')}
                  placeholder="ahmed@eliteproperties.ae"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Agency Name</label>
                <input
                  required
                  value={form.agency}
                  onChange={set('agency')}
                  placeholder="Elite Properties Dubai"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Phone / WhatsApp</label>
                <input
                  required
                  value={form.phone}
                  onChange={set('phone')}
                  placeholder="+971 50 123 4567"
                  className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
                />
              </div>

              {error && <p className="text-xs text-red-500">{error}</p>}

              <button
                type="submit"
                disabled={loading}
                className="w-full bg-navy-600 text-white font-semibold py-3 rounded-xl hover:bg-navy-700 transition-colors disabled:opacity-60 mt-2"
              >
                {loading ? 'Sending…' : 'Request Demo →'}
              </button>

              <p className="text-center text-xs text-gray-400">
                $136/month · Includes full setup · No contracts
              </p>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
