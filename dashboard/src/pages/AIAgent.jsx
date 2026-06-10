import { useState, useRef, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { Send, Phone, Mic, PhoneCall, Bot, MessageSquare, Info } from 'lucide-react'

const BASE = import.meta.env.VITE_API_URL || '/api'

async function authHeaders() {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  return token ? { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' }
}

export default function AIAgent() {
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      content: "Hi! I'm your AI receptionist for Pinnacle Property Management. Ask me about any of our Houston listings, neighborhoods, or schedule a showing.",
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sessionId] = useState(() => `demo-${Date.now()}`)
  const bottomRef = useRef(null)
  const isFirstRender = useRef(true)

  useEffect(() => {
    if (isFirstRender.current) { isFirstRender.current = false; return }
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendMessage(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)

    try {
      const headers = await authHeaders()
      const res = await fetch(`${BASE}/chat/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ message: text, session_id: sessionId }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply || data.detail || 'Sorry, something went wrong.' }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Connection error. Make sure the API is running.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="px-4 md:px-8 py-5 md:py-6 border-b border-gray-200 bg-white">
        <h1 className="text-2xl font-semibold text-gray-900">AI Agent</h1>
        <p className="text-sm text-gray-500 mt-1">Live chat demo · Voice agent setup</p>
      </div>

      <div className="flex-1 flex flex-col md:flex-row gap-4 md:gap-6 p-4 md:p-8 min-h-0 overflow-y-auto md:overflow-hidden">

        {/* ── Chat Widget ─────────────────────────────── */}
        <div className="flex-1 flex flex-col bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-gray-100">
            <div className="w-8 h-8 bg-accent rounded-full flex items-center justify-center">
              <Bot className="w-4 h-4 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-900">AI Receptionist</p>
              <p className="text-xs text-green-500 flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full inline-block" />
                Online
              </p>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
            {messages.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[80%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                    msg.role === 'user'
                      ? 'bg-accent text-white rounded-br-sm'
                      : 'bg-gray-100 text-gray-800 rounded-bl-sm'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 flex gap-1">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <form onSubmit={sendMessage} className="px-4 py-3 border-t border-gray-100 flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Ask about properties, pricing, availability..."
              className="flex-1 px-4 py-2 text-sm border border-gray-200 rounded-full outline-none focus:border-accent transition-colors"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="w-9 h-9 bg-accent text-white rounded-full flex items-center justify-center hover:bg-accent/90 disabled:opacity-40 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>

        {/* ── Voice Agent Panel ────────────────────────── */}
        <div className="w-full md:w-80 flex flex-col gap-4 flex-shrink-0">

          {/* Status card */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-navy-600 rounded-xl flex items-center justify-center">
                <PhoneCall className="w-5 h-5 text-white" />
              </div>
              <div>
                <p className="text-sm font-semibold text-gray-900">Voice Agent</p>
                <p className="text-xs text-gray-400">Twilio · Deepgram · ElevenLabs</p>
              </div>
            </div>

            <div className="space-y-2 mb-4">
              {[
                { label: 'Speech-to-Text', key: 'STT_API_KEY', service: 'Deepgram' },
                { label: 'Text-to-Speech', key: 'TTS_API_KEY', service: 'ElevenLabs' },
                { label: 'Phone Number', key: 'TELEPHONY_PHONE_NUMBER', service: 'Twilio' },
              ].map(item => (
                <div key={item.key} className="flex items-center justify-between py-1.5">
                  <span className="text-xs text-gray-500">{item.label}</span>
                  <span className="text-xs font-medium text-amber-500 bg-amber-50 px-2 py-0.5 rounded-full">
                    Not configured
                  </span>
                </div>
              ))}
            </div>

            <div className="bg-gray-50 rounded-lg p-3">
              <p className="text-xs text-gray-500 leading-relaxed">
                Add your Twilio number below to activate inbound call handling. The AI will answer, qualify leads, and log every call automatically.
              </p>
            </div>
          </div>

          {/* Phone number input */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <label className="text-xs font-semibold text-gray-700 uppercase tracking-wide block mb-3">
              Your Twilio Phone Number
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="+1 (713) 000-0000"
                className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-accent transition-colors"
                disabled
              />
              <button
                disabled
                className="px-3 py-2 bg-gray-100 text-gray-400 text-xs rounded-lg cursor-not-allowed"
              >
                Save
              </button>
            </div>
            <p className="text-xs text-gray-400 mt-2 flex items-start gap-1">
              <Info className="w-3 h-3 mt-0.5 flex-shrink-0" />
              Configure STT and TTS API keys in Settings to enable voice.
            </p>
          </div>

          {/* How it works */}
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
            <p className="text-xs font-semibold text-gray-700 uppercase tracking-wide mb-3">How Voice Works</p>
            <div className="space-y-3">
              {[
                { icon: Phone, text: 'Prospect calls your Twilio number' },
                { icon: Mic, text: 'Deepgram transcribes speech in real-time' },
                { icon: MessageSquare, text: 'AI responds using your property knowledge base' },
                { icon: Bot, text: 'ElevenLabs converts reply to natural speech' },
              ].map(({ icon: Icon, text }, i) => (
                <div key={i} className="flex items-start gap-3">
                  <div className="w-6 h-6 bg-gray-100 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Icon className="w-3 h-3 text-gray-500" />
                  </div>
                  <p className="text-xs text-gray-600 leading-relaxed">{text}</p>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
