import { useState, useRef, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Send, CheckCircle, Circle, Phone, ArrowRight, Sparkles } from 'lucide-react'
import { api } from '../lib/api'

const OPENING = {
  role: 'assistant',
  content: "Hi! I'm Nexa, your NexaDesk setup assistant. I'll help you configure your AI receptionist in about 5 minutes. Let's start — what's the name of your real estate agency and where are you based?",
}

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

export default function Setup() {
  const navigate = useNavigate()
  const [messages, setMessages] = useState([{ ...OPENING, time: now() }])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [extracted, setExtracted] = useState({})
  const [complete, setComplete] = useState(false)
  const [saving, setSaving] = useState(false)
  const [receptionist, setReceptionist] = useState('')
  const [agencyName, setAgencyName] = useState('')
  const messagesRef = useRef(null)

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

    // Build clean API message list (no `time` field)
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
      }
    } catch (err) {
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

  if (complete && !saving) {
    return (
      <div className="min-h-screen bg-navy-600 flex items-center justify-center px-6">
        <div className="bg-white rounded-2xl shadow-xl p-10 max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-5">
            <CheckCircle className="w-8 h-8 text-green-500" />
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            {receptionist} is ready!
          </h1>
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

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">

      {/* Top bar */}
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
              <div
                className="h-full bg-accent rounded-full transition-all duration-500"
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="text-xs text-white/60">{pct}%</span>
          </div>
          <Link to="/dashboard" className="text-xs text-white/40 hover:text-white/70 transition-colors">
            Skip for now
          </Link>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex gap-0 max-w-5xl w-full mx-auto px-4 py-6 gap-6">

        {/* Chat panel */}
        <div className="flex-1 flex flex-col bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden min-h-0">

          {/* Nexa header */}
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

          {/* Messages */}
          <div
            ref={messagesRef}
            className="flex-1 overflow-y-auto p-5 flex flex-col gap-3"
            style={{ minHeight: 0 }}
          >
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex flex-col gap-0.5 max-w-[82%] ${m.role === 'user' ? 'self-end' : 'self-start'}`}
              >
                <div className={`px-4 py-2.5 text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-navy-600 text-white rounded-2xl rounded-br-sm'
                    : 'bg-gray-100 text-gray-800 rounded-2xl rounded-bl-sm'
                }`}>
                  {m.content}
                </div>
                <span className={`text-[10px] text-gray-400 ${m.role === 'user' ? 'text-right' : ''}`}>
                  {m.time}
                </span>
              </div>
            ))}
            {typing && (
              <div className="self-start flex gap-1 px-4 py-3 bg-gray-100 rounded-2xl rounded-bl-sm">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Input */}
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

        {/* Progress panel */}
        <div className="hidden md:flex flex-col w-60 flex-shrink-0 gap-4">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">
              Setup progress
            </p>
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
                          <span className={`text-xs ${done ? 'text-gray-700 font-medium' : 'text-gray-400'}`}>
                            {f.label}
                          </span>
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
