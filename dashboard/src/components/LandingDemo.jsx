import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'

const OPENING_MSG = "Good day! I'm the AI receptionist for Palm Elite Properties. Are you looking to buy, rent, or would you like to schedule a viewing today?"

function respond(input) {
  const s = input.toLowerCase()
  if (/buy|purchase|invest/.test(s))
    return "Great choice! Are you looking in Dubai, Abu Dhabi, or another emirate? We have apartments in Downtown Dubai from AED 1.5M and villas in Arabian Ranches from AED 3.2M."
  if (/rent|lease/.test(s))
    return "Happy to help with rentals. Which area are you considering? Dubai Marina 1BR starts from AED 75K/year, Business Bay from AED 65K/year. When would you like to move in?"
  if (/viewing|visit|see|tour/.test(s))
    return "I can arrange that right now. Which property are you interested in, and what day works best for you? An agent will confirm within the hour."
  if (/price|cost|aed|how much|rate/.test(s))
    return "Prices vary by area — Downtown Dubai 2BR from AED 2.1M, Dubai Marina 1BR from AED 1.2M, JVC from AED 650K. Which area interests you most?"
  if (/downtown|burj|khalifa/.test(s))
    return "Downtown Dubai is premium — studios from AED 950K, 1BR from AED 1.5M, 2BR from AED 2.1M. Burj Khalifa views add 15–20% to the price. Want me to arrange a viewing?"
  if (/marina|jbr|jumeirah beach/.test(s))
    return "Dubai Marina and JBR are very popular. 1BR apartments from AED 1.1M, 2BR from AED 1.7M. Waterfront units are limited. Shall I check current availability?"
  if (/villa|house|townhouse/.test(s))
    return "For villas: Arabian Ranches from AED 3.2M, Palm Jumeirah from AED 12M, Damac Hills from AED 2.4M. How many bedrooms are you looking for?"
  if (/business bay|bay/.test(s))
    return "Business Bay is excellent value — 1BR from AED 950K (sale) or AED 65K/year (rent). Waterfront Business Bay units go from AED 1.4M. Shall I share listings?"
  if (/hello|hi|hey|good/.test(s))
    return "Welcome! Are you looking to buy, rent, or just exploring what's available in the UAE property market?"
  if (/whatsapp|call|contact|agent|human|talk/.test(s))
    return "Of course! I'll connect you with one of our agents right away. Can I take your name and a contact number?"
  if (/abu dhabi/.test(s))
    return "Abu Dhabi is a great market. Saadiyat Island from AED 2M, Al Reem Island from AED 900K, Yas Island from AED 1.1M. Should I have an Abu Dhabi specialist reach out?"
  if (/sharjah/.test(s))
    return "Sharjah offers excellent value — 2BR apartments from AED 400K, villas from AED 1.5M. It's popular for families. Would you like more details?"
  return "Understood. Let me connect you with the right agent. Can I take your name and contact number so we can follow up promptly?"
}

export default function LandingDemo() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [initialized, setInitialized] = useState(false)
  const bottomRef = useRef(null)
  const inputRef = useRef(null)

  function now() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  function handleOpen() {
    setOpen(true)
    if (!initialized) {
      setInitialized(true)
      setTimeout(() => {
        setMessages([{ role: 'bot', text: OPENING_MSG, time: now() }])
      }, 300)
    }
    setTimeout(() => inputRef.current?.focus(), 350)
  }

  function handleSend() {
    const text = input.trim()
    if (!text || typing) return
    setMessages(prev => [...prev, { role: 'user', text, time: now() }])
    setInput('')
    setTyping(true)
    setTimeout(() => {
      setTyping(false)
      setMessages(prev => [...prev, { role: 'bot', text: respond(text), time: now() }])
    }, 800)
  }

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, typing])

  if (!open) {
    return (
      <div className="text-center">
        <button
          onClick={handleOpen}
          className="inline-flex items-center gap-2 text-sm text-accent border border-accent/40 px-6 py-3 rounded-xl hover:bg-accent/5 transition-colors font-medium"
        >
          Try a simulated conversation →
        </button>
        <p className="text-xs text-gray-400 mt-2">No signup needed — see exactly what your clients experience</p>
      </div>
    )
  }

  return (
    <div className="max-w-sm mx-auto">
      <div className="border border-gray-200 rounded-2xl overflow-hidden shadow-lg">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 bg-navy-600">
          <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-white text-xs font-bold flex-shrink-0">N</div>
          <div className="flex-1">
            <span className="text-sm font-semibold text-white block leading-tight">NexaDesk AI</span>
            <span className="flex items-center gap-1 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block animate-pulse" />
              online
            </span>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="text-white/40 hover:text-white text-xs transition-colors"
          >
            Close ↑
          </button>
        </div>

        {/* Messages */}
        <div className="p-4 h-52 overflow-y-auto flex flex-col gap-3 bg-gray-50">
          {messages.map((m, i) => (
            <div key={i} className={`flex flex-col gap-0.5 max-w-[85%] ${m.role === 'user' ? 'self-end' : 'self-start'}`}>
              <div className={`px-3 py-2 text-sm leading-relaxed ${
                m.role === 'user'
                  ? 'bg-accent text-white rounded-2xl rounded-br-sm'
                  : 'bg-white border border-gray-200 text-gray-800 rounded-2xl rounded-bl-sm shadow-sm'
              }`}>
                {m.text}
              </div>
              <span className={`text-[10px] text-gray-400 ${m.role === 'user' ? 'text-right' : ''}`}>{m.time}</span>
            </div>
          ))}
          {typing && (
            <div className="self-start flex gap-1 px-3 py-2.5 bg-white border border-gray-200 rounded-2xl rounded-bl-sm shadow-sm">
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }}
                />
              ))}
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="flex gap-2 px-3 py-3 bg-white border-t border-gray-100">
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSend() } }}
            placeholder="Type a message…"
            className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-accent transition-colors bg-gray-50"
          />
          <button
            onClick={handleSend}
            disabled={!input.trim() || typing}
            className="w-9 h-9 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-40 transition-colors flex items-center justify-center flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
      <p className="text-xs text-gray-400 mt-2.5 text-center italic">
        Simulated demo — the real system handles full conversations via phone &amp; live chat.
      </p>
    </div>
  )
}
