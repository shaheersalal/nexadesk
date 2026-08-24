import { useState, useEffect, useRef } from 'react'
import { X, Send, Tag, CheckCircle } from 'lucide-react'

import { API_BASE as API } from '../lib/apiBase'

const GREETING = "Hi! I'm Nexa. I see you're checking out the pricing — is there something specific holding you back, or would you like to tell me a bit more about your agency?"

// Conversational bridge responses shown between the 10% and 20% offers
// so Nexa doesn't immediately double-down after the first offer.
const BRIDGE = [
  "That makes sense — I appreciate you sharing that. Is there anything else about the plan or features you'd like me to clarify?",
  "Got it. Let me see what else I can do. Could you tell me a bit more about what your agency needs?",
]

function getSessionId() {
  let id = sessionStorage.getItem('nexadesk_discount_session')
  if (!id) {
    id = crypto.randomUUID()
    sessionStorage.setItem('nexadesk_discount_session', id)
  }
  return id
}

export default function DiscountChat({ plan, onClose }) {
  const [messages, setMessages]           = useState([{ role: 'bot', text: GREETING }])
  const [input, setInput]                 = useState('')
  const [loading, setLoading]             = useState(false)
  const [final, setFinal]                 = useState(false)
  const [currentPrice, setCurrentPrice]   = useState(plan.price)
  const [discountPct, setDiscountPct]     = useState(null)   // 10 or 20 once offered
  const [confirmed, setConfirmed]         = useState(false)  // user clicked "Proceed"
  const [msgsSince10, setMsgsSince10]     = useState(0)      // user messages after 10% was given
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function requestDiscount(userMessage = '') {
    setLoading(true)
    try {
      const res = await fetch(`${API}/pricing/discount`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: getSessionId(),
          plan_price:   plan.price,
          user_message: userMessage,
        }),
      })
      const data = await res.json()
      setMessages(prev => [...prev, { role: 'bot', text: data.message, isOffer: true, pct: data.discount_pct, price: data.discounted_price }])
      setCurrentPrice(data.discounted_price)
      setDiscountPct(data.discount_pct)
      if (data.final) setFinal(true)
    } catch {
      setMessages(prev => [
        ...prev,
        { role: 'bot', text: "Sorry, something went wrong on our end — email shaheersalal@gmail.com and we'll sort out a price for you." },
      ])
    } finally {
      setLoading(false)
    }
  }

  function addBridge(index) {
    setMessages(prev => [...prev, { role: 'bot', text: BRIDGE[index % BRIDGE.length] }])
  }

  function handleConfirm() {
    setConfirmed(true)
    // Persist so the sign-up form can include it in the /book-demo request
    sessionStorage.setItem('nexadesk_confirmed_discount', JSON.stringify({
      discount_pct:  discountPct,
      original_price: plan.price,
      final_price:   currentPrice,
      plan_name:     plan.name,
    }))
    setMessages(prev => [
      ...prev,
      {
        role: 'bot',
        text: `✅ Done! Your ${discountPct}% discount is locked in — your plan is now $${currentPrice.toFixed(2)}/mo. We'll send the confirmation to your email once you complete sign-up.`,
        isConfirmation: true,
      },
    ])
    setTimeout(() => onClose?.(), 4000)
  }

  function handleSend(e) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading || final || confirmed) return

    setMessages(prev => [...prev, { role: 'user', text }])
    setInput('')

    if (discountPct === null) {
      // No discount given yet — first real message → offer 10%
      requestDiscount(text)
    } else if (discountPct === 10) {
      // 10% already offered — wait for 2 user messages before offering 20%
      const count = msgsSince10 + 1
      setMsgsSince10(count)
      if (count < 2) {
        // Not yet — respond conversationally
        setTimeout(() => addBridge(count - 1), 600)
      } else {
        // 2 messages in → escalate to 20%
        requestDiscount(text)
      }
    } else {
      // 20% offered and user is still pushing — final response
      requestDiscount(text)
    }
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
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 bg-navy-600 flex-shrink-0">
          <div className="flex items-center gap-2">
            <Tag className="w-4 h-4 text-accent" />
            <div>
              <p className="text-sm font-semibold text-white">Nexa — Pricing</p>
              <p className="text-xs text-gray-400 mt-0.5">
                ${currentPrice.toFixed(2)}/mo{currentPrice < plan.price ? ` (${discountPct}% off)` : ''}
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-gray-50">
          {messages.map((m, i) => (
            <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
              <div
                className={`max-w-[85%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-accent text-white rounded-br-sm'
                    : m.isConfirmation
                    ? 'bg-green-50 border border-green-200 text-green-800 rounded-bl-sm'
                    : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
                }`}
              >
                {m.text}
              </div>

              {/* Proceed button shown under each discount offer (until confirmed) */}
              {m.isOffer && !confirmed && !final && (
                <button
                  onClick={handleConfirm}
                  className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-50 border border-green-200 px-3 py-1.5 rounded-full hover:bg-green-100 transition-colors"
                >
                  <CheckCircle className="w-3.5 h-3.5" />
                  Proceed with {m.pct}% off — ${m.price.toFixed(2)}/mo
                </button>
              )}

              {/* Final offer — same button */}
              {m.isOffer && !confirmed && final && (
                <button
                  onClick={handleConfirm}
                  className="mt-2 flex items-center gap-1.5 text-xs font-semibold text-green-700 bg-green-50 border border-green-200 px-3 py-1.5 rounded-full hover:bg-green-100 transition-colors"
                >
                  <CheckCircle className="w-3.5 h-3.5" />
                  Accept best offer — ${m.price.toFixed(2)}/mo
                </button>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="flex gap-1 px-3 py-2.5 bg-white border border-gray-200 rounded-2xl rounded-bl-sm shadow-sm">
                {[0, 1, 2].map(i => (
                  <span key={i} className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                    style={{ animationDelay: `${i * 0.15}s` }} />
                ))}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form onSubmit={handleSend} className="px-4 py-3 border-t border-gray-100 bg-white flex gap-2 flex-shrink-0">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={confirmed ? 'Discount confirmed!' : final ? "That's our best offer" : 'Tell me more…'}
            disabled={loading || confirmed}
            className="flex-1 px-4 py-2 text-sm border border-gray-200 rounded-full outline-none focus:border-accent transition-colors disabled:opacity-50 disabled:bg-gray-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || loading || confirmed}
            className="w-9 h-9 bg-accent text-white rounded-full flex items-center justify-center hover:bg-accent-dark disabled:opacity-40 transition-colors flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  )
}
