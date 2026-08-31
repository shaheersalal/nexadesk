import { useState, useRef, useEffect } from 'react'
import { MessageCircle, X, Send } from 'lucide-react'
import { api } from '../lib/api'
import { supabase } from '../lib/supabase'

const OPENING = "Hi! I'm your NexaDesk assistant. Ask me anything about your dashboard, leads, knowledge base, settings, or how to get the most from your AI receptionist."

export default function AssistantChat() {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [typing, setTyping] = useState(false)
  const [userEmail, setUserEmail] = useState('')
  const messagesRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user?.email) setUserEmail(data.user.email)
    })
  }, [])

  useEffect(() => {
    if (open && messages.length === 0) {
      setMessages([{ role: 'assistant', content: OPENING }])
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }, [open])

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages, typing])

  useEffect(() => {
    function onKey(e) { if (e.key === 'Escape') handleClose() }
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, messages])

  async function handleClose() {
    setOpen(false)
    const convo = messages.filter(m => m.role !== 'assistant' || messages.indexOf(m) > 0)
    if (convo.filter(m => m.role === 'user').length > 0) {
      api.assistantNotify({ messages, user_email: userEmail }).catch(() => {})
    }
  }

  async function handleSend() {
    const text = input.trim()
    if (!text || typing) return
    const updated = [...messages, { role: 'user', content: text }]
    setMessages(updated)
    setInput('')
    setTyping(true)
    try {
      const res = await api.assistantChat({ messages: updated.filter(m => m.role !== 'system') })
      setMessages(prev => [...prev, { role: 'assistant', content: res.response }])
    } catch {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Something went wrong. Try again or email shaheersalal@gmail.com.' }])
    } finally {
      setTyping(false)
    }
  }

  return (
    <>
      {/* Floating bubble */}
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-6 right-6 z-[55] w-14 h-14 bg-navy-600 text-white rounded-full shadow-lg hover:bg-navy-700 transition-colors flex items-center justify-center group"
          title="Assistant"
        >
          <MessageCircle className="w-6 h-6" />
          <span className="absolute -top-8 right-0 bg-inverse text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none">
            Assistant
          </span>
        </button>
      )}

      {/* Chat panel */}
      {open && (
        <div className="fixed bottom-6 right-6 z-[55] w-80 sm:w-96 flex flex-col rounded-2xl shadow-2xl overflow-hidden border border-gray-200 bg-surface">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-navy-600 flex-shrink-0">
            <div>
              <p className="text-sm font-semibold text-white">Assistant</p>
              <p className="text-xs text-gray-400">NexaDesk help & guidance</p>
            </div>
            <button onClick={handleClose} className="text-gray-400 hover:text-white transition-colors">
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Messages */}
          <div
            ref={messagesRef}
            className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-gray-50 max-h-80"
          >
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
                  m.role === 'user'
                    ? 'bg-accent text-white rounded-br-sm'
                    : 'bg-surface border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
                }`}>
                  {m.content}
                </div>
              </div>
            ))}
            {typing && (
              <div className="flex justify-start">
                <div className="flex gap-1 px-3 py-2.5 bg-surface border border-gray-200 rounded-2xl rounded-bl-sm shadow-sm">
                  {[0, 1, 2].map(i => (
                    <span key={i} className="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Input */}
          <div className="flex gap-2 px-3 py-3 bg-surface border-t border-gray-100 flex-shrink-0">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleSend() } }}
              placeholder="Ask anything…"
              disabled={typing}
              className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 outline-none focus:border-accent transition-colors bg-gray-50 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || typing}
              className="w-9 h-9 bg-accent text-white rounded-lg hover:bg-accent/90 disabled:opacity-40 transition-colors flex items-center justify-center flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </>
  )
}
