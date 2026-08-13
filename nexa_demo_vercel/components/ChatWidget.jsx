'use client'
import { useState, useRef, useEffect } from 'react'
import { postJSON } from '@/lib/api'

export default function ChatWidget() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: "Hi! I'm Nexa, your property advisor for Pinnacle Property Management. Are you looking to buy, rent, or invest — and which market interests you most?" },
  ])
  const [input, setInput]     = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef             = useRef(null)

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    const updated = [...messages, { role: 'user', content: text }]
    setMessages(updated)
    setInput('')
    setLoading(true)
    try {
      // Real backend — same prompt, model and rate limits as production.
      const data = await postJSON('/demo/chat', { messages: updated })
      setMessages(m => [...m, { role: 'assistant', content: data.response || 'Sorry, something went wrong.' }])
    } catch (err) {
      // Surface the server's message (rate limit, validation) rather than a
      // blanket "network error" that hides why the demo stopped responding.
      setMessages(m => [...m, { role: 'assistant', content: err.message || 'Network error — please try again.' }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto space-y-3 pr-1 mb-3" style={{ maxHeight: '340px' }}>
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
              m.role === 'user'
                ? 'bg-accent text-white rounded-br-sm'
                : 'bg-gray-100 text-gray-800 rounded-bl-sm'
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3 text-gray-400 text-sm">
              <span className="animate-pulse">Nexa is typing…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && send()}
          placeholder="Type your message…"
          disabled={loading}
          className="flex-1 border border-gray-200 rounded-xl px-3.5 py-2.5 text-sm outline-none focus:border-accent transition-colors disabled:opacity-50"
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          className="bg-accent text-white px-4 py-2.5 rounded-xl text-sm font-medium hover:bg-accent-light transition-colors disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  )
}
