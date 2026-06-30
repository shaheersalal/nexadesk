import { useState, useEffect, useRef } from 'react'
import { X, Send, Tag } from 'lucide-react'

const API = 'https://shaheersalal-nexadesk.hf.space'

function getSessionId() {
  let id = sessionStorage.getItem('nexadesk_discount_session')
  if (!id) {
    id = crypto.randomUUID()
    sessionStorage.setItem('nexadesk_discount_session', id)
  }
  return id
}

export default function DiscountChat({ plan, onClose }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [final, setFinal] = useState(false)
  const [currentPrice, setCurrentPrice] = useState(plan.price)
  const bottomRef = useRef(null)
  const startedRef = useRef(false)

  async function requestDiscount(userMessage = '') {
    setLoading(true)
    try {
      const res = await fetch(`${API}/pricing/discount`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: getSessionId(),
          plan_price: plan.price,
          user_message: userMessage,
        }),
      })
      const data = await res.json()
      // discount_pct / discounted_price always come from the structured API
      // response, never parsed from the LLM's `message` text — see
      // app/pricing/router.py for the deterministic state machine this calls.
      setMessages(prev => [...prev, { role: 'bot', text: data.message }])
      setCurrentPrice(data.discounted_price)
      if (data.final) {
        setFinal(true)
        setTimeout(() => onClose?.(), 6000)
      }
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'bot', text: "Sorry, something went wrong on our end — email shaheersalal@gmail.com and we'll sort out a price for you." },
      ])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (startedRef.current) return
    startedRef.current = true
    requestDiscount()
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading || final) return
    setMessages(prev => [...prev, { role: 'user', text }])
    setInput('')
    requestDiscount(text)
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 z-[60] flex items-end sm:items-center sm:justify-end p-0 sm:p-6"
      onClick={onClose}
    >
      <div
        className="bg-white w-full sm:w-96 h-[520px] rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 bg-navy-600 flex-shrink-0">
          <div className="flex items-center gap-2">
            <Tag className="w-4 h-4 text-accent" />
            <div>
              <p className="text-sm font-semibold text-white">Nexa — Pricing</p>
              <p className="text-xs text-gray-400 mt-0.5">
                ${currentPrice.toFixed(2)}/mo{currentPrice < plan.price ? ' (discounted)' : ''}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-gray-50">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div
                className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-accent text-white rounded-br-sm'
                    : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
                }`}
              >
                {m.text}
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="flex gap-1 px-3 py-2.5 bg-white border border-gray-200 rounded-2xl rounded-bl-sm shadow-sm">
                {[0, 1, 2].map(i => (
                  <span
                    key={i}
                    className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }}
                  />
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={handleSend} className="px-4 py-3 border-t border-gray-100 bg-white flex gap-2 flex-shrink-0">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={final ? "That's our best offer" : 'Can you do better?'}
            disabled={loading || final}
            className="flex-1 px-4 py-2 text-sm border border-gray-200 rounded-full outline-none focus:border-accent transition-colors disabled:opacity-50 disabled:bg-gray-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading || final}
            className="w-9 h-9 bg-accent text-white rounded-full flex items-center justify-center hover:bg-accent-dark disabled:opacity-40 transition-colors flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  )
}
