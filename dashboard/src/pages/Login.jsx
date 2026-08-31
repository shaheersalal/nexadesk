import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { supabase } from '../lib/supabase'
import { Phone, Info } from 'lucide-react'

export default function Login() {
  const [searchParams] = useSearchParams()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [mode, setMode] = useState(searchParams.get('mode') === 'signup' ? 'signup' : 'login')

  const appName = import.meta.env.VITE_APP_NAME || 'NexaDesk'

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')

    const authCall = mode === 'login'
      ? supabase.auth.signInWithPassword({ email, password })
      : supabase.auth.signUp({ email, password })

    // No silent background retry — if it doesn't resolve quickly, surface a
    // direct message and stop, rather than leaving the button stuck on
    // "Please wait…" indefinitely.
    const timeout = new Promise((resolve) =>
      setTimeout(() => resolve({ error: { message: 'TIMEOUT' } }), 5000)
    )

    const { error } = await Promise.race([authCall, timeout])

    if (error) {
      setError(
        error.message === 'TIMEOUT'
          ? "That's taking longer than it should — please try again in a few minutes."
          : error.message
      )
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-navy-600 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-8">
          <Phone className="w-7 h-7 text-accent-ink" />
          <span className="text-white text-2xl font-semibold">{appName}</span>
        </div>

        <div className="bg-surface rounded-2xl shadow-xl p-8">
          <h1 className="text-xl font-semibold text-gray-900 mb-1">
            {mode === 'login' ? 'Welcome back' : 'Create your account'}
          </h1>
          <p className="text-gray-500 text-sm mb-6">
            {mode === 'login' ? 'Sign in to your dashboard' : 'Get full dashboard access instantly'}
          </p>

          {mode === 'signup' && (
            <div className="mb-5 flex gap-3 p-3.5 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-800 leading-relaxed">
              <Info className="w-4 h-4 text-amber-500 flex-shrink-0 mt-0.5" />
              <span>
                <strong>Quick heads-up:</strong> to activate the AI phone receptionist and live chat, you'll need to set up an AI phone number and a few supporting services. The dashboard is free to explore right now — costs only apply when you go live. We walk you through every step.
              </span>
            </div>
          )}

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
                placeholder="you@example.com"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
                placeholder="••••••••"
                required
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-2.5 text-sm"
            >
              {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <p className="mt-4 text-center text-sm text-gray-500">
            {mode === 'login' ? "Don't have an account? " : 'Already have one? '}
            <button
              onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
              className="text-accent-ink font-medium hover:underline"
            >
              {mode === 'login' ? 'Sign up' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  )
}
