import { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { CheckCircle, Phone, ArrowRight, Sparkles, Eye, EyeOff } from 'lucide-react'
import { supabase } from '../lib/supabase'
import { api } from '../lib/api'

// ── Onboarding form config ────────────────────────────────────────────────────
// Just two questions — lead source(s) and the AI persona name. Everything else
// uses product-wide defaults and can be edited later from Settings.

const LEAD_SOURCE_LABELS = {
  property_portal_ads: 'Property portal ads (Bayut, Property Finder, etc.)',
  facebook_instagram_ads: 'Facebook / Instagram ads',
  google_ads: 'Google ads',
  website_organic: 'Website / organic',
  referrals: 'Referrals',
  walk_in: 'Walk-in',
  other: 'Other',
}

// ── Set Password screen ───────────────────────────────────────────────────────

function SetPasswordScreen({ meta, onDone }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    if (password.length < 8) { setError('Password must be at least 8 characters.'); return }
    if (password !== confirm) { setError('Passwords do not match.'); return }
    setLoading(true)
    setError('')
    const { error: err } = await supabase.auth.updateUser({ password })
    if (err) { setError(err.message); setLoading(false); return }
    onDone(meta)
  }

  const inputClass = 'w-full border border-gray-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:border-navy-600 transition-colors bg-gray-50'

  return (
    <div className="min-h-screen bg-gradient-to-b from-navy-600 to-navy-700 flex items-center justify-center px-4">
      <div className="bg-surface rounded-2xl shadow-2xl p-8 md:p-10 w-full max-w-md">
        <div className="flex items-center gap-2 mb-8">
          <div className="w-8 h-8 bg-navy-600 rounded-lg flex items-center justify-center">
            <Phone className="w-4 h-4 text-accent-ink" />
          </div>
          <span className="font-semibold text-gray-900">NexaDesk</span>
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-1">
          Welcome{meta.full_name ? `, ${meta.full_name.split(' ')[0]}` : ''}!
        </h1>
        <p className="text-gray-500 text-sm mb-6">Set your password to activate your account.</p>

        {/* Pre-filled info */}
        {(meta.agency_name || meta.phone) && (
          <div className="bg-gray-50 rounded-xl p-4 mb-6 space-y-2">
            {meta.full_name && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Name</span>
                <span className="font-medium text-gray-700">{meta.full_name}</span>
              </div>
            )}
            {meta.agency_name && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Agency</span>
                <span className="font-medium text-gray-700">{meta.agency_name}</span>
              </div>
            )}
            {meta.phone && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Phone</span>
                <span className="font-medium text-gray-700">{meta.phone}</span>
              </div>
            )}
            {meta.country && (
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Country</span>
                <span className="font-medium text-gray-700">{meta.country}</span>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="relative">
            <input
              type={showPw ? 'text' : 'password'}
              className={inputClass}
              placeholder="Set a password (min. 8 characters)"
              value={password}
              onChange={e => setPassword(e.target.value)}
              autoFocus
            />
            <button type="button" onClick={() => setShowPw(v => !v)}
              className="absolute right-3 top-3 text-gray-400 hover:text-gray-600">
              {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
          <input
            type={showPw ? 'text' : 'password'}
            className={inputClass}
            placeholder="Confirm password"
            value={confirm}
            onChange={e => setConfirm(e.target.value)}
          />

          {error && <p className="text-red-500 text-xs">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 bg-navy-600 text-white font-semibold py-3 rounded-xl hover:bg-navy-700 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Activating…' : <><span>Activate Account</span> <ArrowRight className="w-4 h-4" /></>}
          </button>
        </form>
      </div>
    </div>
  )
}

// ── Main Setup page ───────────────────────────────────────────────────────────

export default function Setup() {
  const navigate = useNavigate()

  // Use hash captured by inline script in index.html — runs before ANY
  // module JS so Supabase cannot clear it first
  const [launchHash] = useState(() => window.__launchHash || '')
  const [launchSearch] = useState(() => window.__launchSearch || '')

  // 'loading' | 'set-password' | 'form' | 'done'
  const [stage, setStage] = useState('loading')
  const [inviteMeta, setInviteMeta] = useState({})

  // Form state
  const [leadSources, setLeadSources] = useState([])
  const [receptionistName, setReceptionistName] = useState('Nexa')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    // Supabase clears the URL hash before firing SIGNED_IN, so we use
    // launchHash/launchSearch captured synchronously at mount time.
    const hasInviteToken = launchHash.includes('access_token') || launchSearch.includes('code')

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'INITIAL_SESSION') {
        if (session && !hasInviteToken) {
          setStage('form')
        } else if (!session && !hasInviteToken) {
          navigate('/login', { replace: true })
        }
        // If hasInviteToken: Supabase is still processing it — wait for SIGNED_IN
      } else if (event === 'SIGNED_IN') {
        if (session) {
          if (hasInviteToken) {
            window.history.replaceState(null, '', '/setup')
            setInviteMeta(session.user.user_metadata || {})
            setStage('set-password')
          } else {
            setStage('form')
          }
        }
      }
    })
    return () => subscription.unsubscribe()
  }, [])

  function handlePasswordDone() {
    setStage('form')
  }

  function toggleSource(key) {
    setLeadSources(prev => prev.includes(key) ? prev.filter(s => s !== key) : [...prev, key])
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setSaving(true)
    setError('')
    try {
      await api.onboardingComplete({
        lead_sources: leadSources,
        receptionist_name: receptionistName,
      })
      setStage('done')
    } catch {
      setError("Couldn't save your setup — please try again.")
    } finally {
      setSaving(false)
    }
  }

  // ── Stages ──────────────────────────────────────────────────────────────────

  if (stage === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-navy-600">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (stage === 'set-password') {
    return <SetPasswordScreen meta={inviteMeta} onDone={handlePasswordDone} />
  }

  if (stage === 'done') {
    return (
      <div className="min-h-screen bg-navy-600 flex items-center justify-center px-6">
        <div className="bg-surface rounded-2xl shadow-xl p-10 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-5">
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{receptionistName || 'Nexa'} is ready!</h1>
          <p className="text-gray-500 text-sm mb-8 leading-relaxed">
            Your AI receptionist is set up. Add properties and knowledge base documents to make it even smarter.
          </p>
          <button
            onClick={() => navigate('/dashboard')}
            className="inline-flex items-center gap-2 bg-navy-600 text-white font-semibold px-8 py-3 rounded-xl hover:bg-navy-700 transition-colors w-full justify-center"
          >
            Go to Dashboard <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    )
  }

  // ── Form stage ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <div className="h-14 bg-navy-600 flex items-center justify-between px-6 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-navy-700 rounded-lg flex items-center justify-center">
            <Phone className="w-3.5 h-3.5 text-accent-ink" />
          </div>
          <span className="text-white font-semibold">NexaDesk</span>
        </div>
        <Link to="/dashboard" className="text-xs text-white/40 hover:text-white/70 transition-colors">
          Skip for now
        </Link>
      </div>

      <div className="flex-1 flex items-center justify-center px-4 py-10">
        <form onSubmit={handleSubmit} className="bg-surface rounded-2xl border border-gray-200 shadow-sm p-8 w-full max-w-lg">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-9 h-9 rounded-full bg-navy-600 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-4 h-4 text-accent-ink" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">Two quick questions</p>
              <p className="text-xs text-gray-400">Everything else uses sensible defaults — edit anytime in Settings.</p>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Where do your leads usually come from?
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(LEAD_SOURCE_LABELS).map(([key, label]) => (
                <button
                  type="button"
                  key={key}
                  onClick={() => toggleSource(key)}
                  className={`text-left text-sm px-3 py-2.5 rounded-xl border transition-colors ${
                    leadSources.includes(key)
                      ? 'border-accent bg-accent/10 text-gray-900 font-medium'
                      : 'border-gray-200 text-gray-600 hover:border-gray-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              What should we name your AI receptionist?
            </label>
            <input
              value={receptionistName}
              onChange={e => setReceptionistName(e.target.value)}
              placeholder="Nexa"
              className="w-full text-sm border border-gray-200 rounded-xl px-4 py-3 outline-none focus:border-navy-600 transition-colors"
            />
          </div>

          {error && <p className="text-red-500 text-xs mb-4">{error}</p>}

          <button
            type="submit"
            disabled={saving}
            className="w-full flex items-center justify-center gap-2 bg-navy-600 text-white font-semibold py-3 rounded-xl hover:bg-navy-700 disabled:opacity-50 transition-colors"
          >
            {saving ? 'Saving…' : <><span>Finish setup</span> <ArrowRight className="w-4 h-4" /></>}
          </button>
        </form>
      </div>
    </div>
  )
}
