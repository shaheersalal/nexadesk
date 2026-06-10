import { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { X, Send } from 'lucide-react'

export default function SupportChat({ onClose, onMessagesRead }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [companyId, setCompanyId] = useState(null)
  const [ready, setReady] = useState(false)
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    async function init() {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return
      const { data: ud } = await supabase.from('users').select('company_id').eq('id', user.id).single()
      const cid = ud?.company_id
      if (!cid) return
      setCompanyId(cid)

      const { data: msgs } = await supabase.from('support_messages')
        .select('*').eq('company_id', cid).order('created_at', { ascending: true })
      setMessages(msgs || [])
      setReady(true)

      // mark admin messages as read
      await supabase.from('support_messages')
        .update({ read_by_user: true })
        .eq('company_id', cid).eq('sender_role', 'admin').eq('read_by_user', false)
      onMessagesRead?.()
    }
    init()
  }, [])

  // scroll to bottom on initial load
  useEffect(() => {
    if (ready) bottomRef.current?.scrollIntoView()
  }, [ready])

  // realtime: new messages from admin
  useEffect(() => {
    if (!companyId) return
    const channel = supabase.channel(`support_chat_${companyId}`)
      .on('postgres_changes', {
        event: 'INSERT', schema: 'public', table: 'support_messages',
        filter: `company_id=eq.${companyId}`,
      }, async (payload) => {
        setMessages(prev =>
          prev.find(m => m.id === payload.new.id) ? prev : [...prev, payload.new]
        )
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
        if (payload.new.sender_role === 'admin') {
          await supabase.from('support_messages')
            .update({ read_by_user: true }).eq('id', payload.new.id)
          onMessagesRead?.()
        }
      })
      .subscribe()
    return () => supabase.removeChannel(channel)
  }, [companyId])

  async function sendMessage(e) {
    e.preventDefault()
    if (!input.trim() || !companyId || loading) return
    setLoading(true)
    const content = input.trim()
    setInput('')
    const { data } = await supabase.from('support_messages')
      .insert({ company_id: companyId, sender_role: 'user', content })
      .select().single()
    if (data) {
      setMessages(prev => prev.find(m => m.id === data.id) ? prev : [...prev, data])
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
    setLoading(false)
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 z-50 flex items-end sm:items-center sm:justify-end p-0 sm:p-6"
      onClick={onClose}
    >
      <div
        className="bg-white w-full sm:w-96 h-[540px] rounded-t-2xl sm:rounded-2xl shadow-2xl flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 bg-navy-600 flex-shrink-0">
          <div>
            <p className="text-sm font-semibold text-white">NexaDesk Support</p>
            <p className="text-xs text-gray-400 mt-0.5">We typically reply within a few hours</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3 bg-gray-50">
          {ready && messages.length === 0 && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-2xl rounded-bl-sm px-4 py-2.5 text-sm text-gray-700 max-w-[85%] leading-relaxed shadow-sm">
                Hi! How can we help? Ask about API setup, phone numbers, billing, or anything else.
              </div>
            </div>
          )}
          {messages.map(msg => (
            <div key={msg.id} className={`flex ${msg.sender_role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[82%] px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                msg.sender_role === 'user'
                  ? 'bg-accent text-white rounded-br-sm'
                  : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
              }`}>
                {msg.content}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <form onSubmit={sendMessage} className="px-4 py-3 border-t border-gray-100 bg-white flex gap-2 flex-shrink-0">
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Type your message…"
            autoFocus
            className="flex-1 px-4 py-2 text-sm border border-gray-200 rounded-full outline-none focus:border-accent transition-colors"
            disabled={loading || !companyId}
          />
          <button
            type="submit"
            disabled={!input.trim() || loading || !companyId}
            className="w-9 h-9 bg-accent text-white rounded-full flex items-center justify-center hover:bg-accent/90 disabled:opacity-40 transition-colors flex-shrink-0"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  )
}
