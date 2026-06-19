import { useState, useRef, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Send, CheckCircle, Circle, Phone, ArrowRight, Sparkles, Eye, EyeOff } from 'lucide-react'
import { supabase } from '../lib/supabase'
import { api } from '../lib/api'

// ── Onboarding chat config ────────────────────────────────────────────────────

const PROGRESS_GROUPS = [
  {
    label: 'Agency',
    fields: [
      { key: 'agency_name',    label: 'Agency name' },
      { key: 'city',           label: 'Location' },
      { key: 'working_hours',  label: 'Working hours' },
    ],
  },
  {
    label: 'AI Persona',
    fields: [
      { key: 'receptionist_name', label: 'Receptionist name' },
      { key: 'tone',              label: 'Tone' },
      { key: 'languages',         label: 'Languages' },
    ],
  },
  {
    label: 'Coverage',
    fields: [
      { key: 'services',        label: 'Services' },
      { key: 'areas',           label: 'Areas covered' },
      { key: 'sale_price_min',  label: 'Price ranges' },
    ],
  },
  {
    label: 'Escalation',
    fields: [
      { key: 'escalation_name', label: 'Human contact' },
    ],
  },
]

function isDone(extracted, key) {
  const val = extracted[key]
  if (!val) return false
  if (Array.isArray(val)) return val.length > 0
  return true
}

function totalProgress(extracted) {
  const all = PROGRESS_GROUPS.flatMap(g => g.fields)
  const done = all.filter(f => isDone(extracted, f.key)).length
  return Math.round((done / all.length) * 100)
}

function now() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
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
      <div className="bg-white rounded-2xl shadow-2xl p-8 md:p-10 w-full max-w-md">
        <div className="flex items-center gap-2 mb-8">
          <div className="w-8 h-8 bg-navy-600 rounded-lg flex items-center justify-center">
            <Phone className="w-4 h-4 text-accent" />
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

  // Capture BEFORE Supabase processes and clears the URL hash
  const [launchHash] = useState(() => window.location.hash)
  const [launchSearch] = useState(() => window.location.search)

  // 'loading' | 'set-password' | 'chat' | 'done'
  const [stage, setStage] = useState('loading')
  const [inviteMeta, setInviteMeta] = useState({})
  const [preExtracted, setPreExtracted] = useState({})

  // Chat state
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [extracted, setExtracted] = useState({})
  const [complete, setComplete] = useState(false)
  const [saving, setSaving] = useState(false)
  const [receptionist, setReceptionist] = useState('')
  const [agencyName, setAgencyName] = useState('')
  const messagesRef = useRef(null)

  useEffect(() => {
    // Supabase clears the URL hash before firing SIGNED_IN, so we use
    // launchHash/launchSearch captured synchronously at mount time.
    const hasInviteToken = launchHash.includes('access_token') || launchSearch.includes('code')
    const isInviteType   = launchHash.includes('type=invite')  || launchSearch.includes('type=invite')

    const { data: { subscription } } = supabase.auth.onAuthStateChange((event, session) => {
      if (event === 'INITIAL_SESSION') {
        if (session && !hasInviteToken) {
          // Already logged in, no invite token → go straight to chat
          beginChat(session.user.user_metadata)
        } else if (!session && !hasInviteToken) {
          // Not logged in, no token → send to login
          navigate('/login', { replace: true })
        }
        // If hasInviteToken: Supabase is still processing it — wait for SIGNED_IN
      } else if (event === 'SIGNED_IN') {
        if (session) {
          // Any SIGNED_IN on /setup with a token in the launch URL = invite flow
          if (hasInviteToken) {
            window.history.replaceState(null, '', '/setup')
            setInviteMeta(session.user.user_metadata || {})
            setStage('set-password')
          } else {
            beginChat(session.user.user_metadata)
          }
        }
      }
    })
    return () => subscription.unsubscribe()
  }, [])

  function beginChat(meta = {}) {
    // Pre-seed extracted fields from invite metadata so Nexa skips known answers
    const pre = {}
    if (meta.agency_name) pre.agency_name = meta.agency_name
    setPreExtracted(pre)
    setExtracted(pre)

    const greeting = meta.full_name
      ? `Hi ${meta.full_name.split(' ')[0]}! I'm Nexa, your NexaDesk setup assistant. I'll configure your AI receptionist in about 5 minutes.${meta.agency_name ? ` I can see you're with ${meta.agency_name} — great!` : ''} Where are you based, and what are your working hours?`
      : "Hi! I'm Nexa, your NexaDesk setup assistant. I'll help you configure your AI receptionist in about 5 minutes. Let's start — what's the name of your real estate agency and where are you based?"

    setMessages([{ role: 'assistant', content: greeting, time: now() }])
    setStage('chat')
  }

  function handlePasswordDone(meta) {
    beginChat(meta)
  }

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages, typing])

  async function handleSend() {
    const text = input.trim()
    if (!text || typing) return

    const userMsg = { role: 'user', content: text, time: now() }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setTyping(true)

    const apiMessages = nextMessages.map(({ role, content }) => ({ role, content }))

    try {
      const res = await api.onboardingChat({ messages: apiMessages, extracted })
      const botMsg = { role: 'assistant', content: res.response, time: now() }
      setMessages(prev => [...prev, botMsg])
      setExtracted(res.extracted)

      if (res.complete) {
        setComplete(true)
        setReceptionist(res.extracted.receptionist_name || 'Aria')
        setAgencyName(res.extracted.agency_name || 'your agency')
        setSaving(true)
        await api.onboardingComplete({ extracted: res.extracted })
        setSaving(false)
        setStage('done')
      }
    } catch {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: "I'm having a moment — could you repeat that?",
        time: now(),
      }])
    } finally {
      setTyping(false)
    }
  }

  const pct = totalProgress(extracted)

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

  if (stage === 'done' && !saving) {
    return (
      <div className="min-h-screen bg-navy-600 flex items-center justify-center px-6">
        <div className="bg-white rounded-2xl shadow-xl p-10 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-5">
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">{receptionist} is ready!</h1>
          <p className="text-gray-500 text-sm mb-8 leading-relaxed">
            Your AI receptionist is configured for <strong>{agencyName}</strong>. Add properties and knowledge base documents to make it even smarter.
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

  // ── Chat stage ──────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <div className="h-14 bg-navy-600 flex items-center justify-between px-6 flex-shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-navy-700 rounded-lg flex items-center justify-center">
            <Phone className="w-3.5 h-3.5 text-accent" />
          </div>
          <span className="text-white font-semibold">NexaDesk</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex items-center gap-2">
            <div className="h-1.5 w-28 bg-white/20 rounded-full overflow-hidden">
              <div className="h-full bg-accent rounded-full transition-all duration-500" style={{ width: `${pct}%` }} />
            </div>
            <span className="text-xs text-white/60">{pct}%</span>
          </div>
          <Link to="/dashboard" className="text-xs text-white/40 hover:text-white/70 transition-colors">
            Skip for now
          </Link>
        </div>
      </div>

      <div className="flex-1 flex gap-0 max-w-5xl w-full mx-auto px-4 py-6 gap-6">
        <div className="flex-1 flex flex-col bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden min-h-0">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
            <div className="w-9 h-9 rounded-full bg-navy-600 flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-4 h-4 text-accent" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">Nexa</p>
              <p className="text-xs text-green-500 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block" />
                NexaDesk setup assistant
              </p>
            </div>
          </div>

          <div ref={messagesRef} className="flex-1 overflow-y-auto p-5 flex flex-col gap-3" style={{ minHeight: 0 }}>
            {messages.map((m, i) => (
              <div key={i} className={`flex flex-col gap-0.5 max-w-[82%] ${m.role === 'user' ? 'self-end' : 'self-start'}`}>
                <div className={`px-4 py-2.5 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-navy-600 text-white rounded-2xl rounded-br-sm'
                    : 'bg-gray-100 text-gray-800 rounded-2xl rounded-bl-sm'
                }`}>
                  {m.content}
                </div>
                <span className={`text-[10px] text-gray-400 ${m.role === 'user' ? 'text-right' : ''}`}>{m.time}</span>
              </div>
            ))}
            {typing && (
              <div className="self-start flex gap-1 px-4 py-3 bg-gray-100 rounded-2xl rounded-bl-sm">
                {[0, 1, 2].map(i => (
                  <span key={i} className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            )}
          </div>

          <div className="flex gap-2 px-4 py-3 border-t border-gray-100 bg-white">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSend() } }}
              placeholder="Type your answer…"
              className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2.5 outline-none focus:border-navy-600 transition-colors"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || typing}
              className="w-10 h-10 bg-navy-600 text-white rounded-lg hover:bg-navy-700 disabled:opacity-40 transition-colors flex items-center justify-center flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>

        <div className="hidden md:flex flex-col w-60 flex-shrink-0 gap-4">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">Setup progress</p>
            <div className="space-y-5">
              {PROGRESS_GROUPS.map(group => (
                <div key={group.label}>
                  <p className="text-xs font-medium text-gray-400 mb-2">{group.label}</p>
                  <div className="space-y-2">
                    {group.fields.map(f => {
                      const done = isDone(extracted, f.key)
                      return (
                        <div key={f.key} className="flex items-center gap-2">
                          {done
                            ? <CheckCircle className="w-3.5 h-3.5 text-green-500 flex-shrink-0" />
                            : <Circle className="w-3.5 h-3.5 text-gray-300 flex-shrink-0" />
                          }
                          <span className={`text-xs ${done ? 'text-gray-700 font-medium' : 'text-gray-400'}`}>{f.label}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="bg-accent/10 rounded-2xl p-4 border border-accent/20">
            <p className="text-xs text-amber-900 leading-relaxed">
              Your AI receptionist uses this information to answer client calls. The more complete your setup, the better it performs.
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
