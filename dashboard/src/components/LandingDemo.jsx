import { useState, useRef, useEffect } from 'react'
import { Send } from 'lucide-react'

const API = 'https://shaheersalal-nexadesk.hf.space'

const OPENING_MSG = "Good day! I'm Nexa, the AI receptionist for Palm Elite Properties. Are you looking to buy, rent, or would you like to schedule a viewing today?"

// Fallback if the AI backend is unreachable
function fallback(input) {
  const s = input.toLowerCase()
  if (/buy|purchase|invest|sale/.test(s))
    return "Great! We have options across Dubai — from JVC studios at AED 380K to Palm Jumeirah villas at AED 12M+. What's your approximate budget, and are you looking for an apartment or a villa?"
  if (/rent|lease/.test(s))
    return "Happy to help with rentals. Are you looking for a furnished or unfurnished unit? And which area of Dubai are you considering — closer to the Marina, Business Bay, or somewhere else?"
  if (/viewing|visit|see|tour|book/.test(s))
    return "Absolutely — I can arrange that. Which property caught your eye, and what days work best for you? I'll confirm with one of our agents within the hour."
  if (/price|cost|how much|rate|aed/.test(s))
    return "Prices vary widely by area. Downtown Dubai 1BRs start from AED 1.5M, Marina from AED 900K, and JVC from AED 550K. What area and size are you interested in?"
  if (/downtown|burj/.test(s))
    return "Downtown Dubai is our most prestigious area — 1BRs from AED 1.5M, 2BRs from AED 2.1M. Burj Khalifa-view units carry a 15–20% premium. Would you like to see what's currently available?"
  if (/marina|jbr|jumeirah beach/.test(s))
    return "Dubai Marina and JBR are always in high demand. 1BRs from AED 900K, 2BRs from AED 1.5M — waterfront units move fast. Shall I check availability for a specific size?"
  if (/villa|house|townhouse/.test(s))
    return "For villas, Arabian Ranches starts from AED 3.2M, Dubai Hills from AED 4M for a 4BR. Palm Jumeirah from AED 12M. How many bedrooms does your family need?"
  if (/jvc|affordable|budget/.test(s))
    return "JVC is excellent value — 1BRs from AED 550K and rental yields up to 9%. Very popular with investors. Are you buying to live in or as an investment?"
  if (/abu dhabi/.test(s))
    return "Abu Dhabi is a strong market. Al Reem Island 1BRs from AED 750K, Saadiyat Island from AED 1.2M. Would you like an Abu Dhabi specialist to reach out?"
  if (/invest|yield|return/.test(s))
    return "JVC and JLT offer the best yields — 7–9% gross. Marina and Downtown give 5–7% with stronger capital appreciation. What matters more to you: yield or capital growth?"
  if (/hello|hi|hey|salam|مرحبا/.test(s))
    return "Welcome! Are you looking to buy, rent, or invest in UAE property? I can help with everything from studio apartments to waterfront villas."
  if (/agent|human|speak|call|whatsapp/.test(s))
    return "Of course! I'll connect you with one of our senior agents right away. Can I take your name and a contact number?"
  return "I'd love to help you find the right property. Could you tell me more — are you looking to buy or rent, and do you have a preferred area or budget in mind?"
}

function now() {
  return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function LandingDemo() {
  const [messages, setMessages] = useState([{ role: 'bot', text: OPENING_MSG, time: now() }])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const messagesRef = useRef(null)

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages, typing])

  async function handleSend() {
    const text = input.trim()
    if (!text || typing) return

    setMessages([...messages, { role: 'user', text, time: now() }])
    setInput('')
    setTyping(true)

    // Build conversation history for the AI
    const history = [...messages, { role: 'user', text }].map(m => ({
      role: m.role === 'bot' ? 'assistant' : 'user',
      content: m.text,
    }))

    try {
      const res = await fetch(`${API}/demo/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ messages: history }),
        signal: AbortSignal.timeout(5000),
      })
      if (!res.ok) throw new Error()
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'bot', text: data.response, time: now() }])
    } catch {
      setMessages(prev => [...prev, { role: 'bot', text: fallback(text), time: now() }])
    } finally {
      setTyping(false)
    }
  }

  return (
    <div className="max-w-sm mx-auto">
      <div className="border border-gray-200 rounded-2xl overflow-hidden shadow-lg">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 bg-navy-600">
          <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-white text-xs font-bold flex-shrink-0">N</div>
          <div className="flex-1">
            <span className="text-sm font-semibold text-white block leading-tight">Nexa · Palm Elite Properties</span>
            <span className="flex items-center gap-1 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block animate-pulse" />
              online
            </span>
          </div>
        </div>

        {/* Messages */}
        <div ref={messagesRef} className="p-4 h-56 overflow-y-auto flex flex-col gap-3 bg-gray-50">
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
                <span key={i} className="w-1.5 h-1.5 rounded-full bg-gray-400 inline-block animate-bounce"
                  style={{ animationDelay: `${i * 0.15}s` }} />
              ))}
            </div>
          )}
        </div>

        {/* Input — no autoFocus, safe on mobile */}
        <div className="flex gap-2 px-3 py-3 bg-white border-t border-gray-100">
          <input
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
        Live AI demo — speaks your client's language, automatically.
      </p>
    </div>
  )
}
