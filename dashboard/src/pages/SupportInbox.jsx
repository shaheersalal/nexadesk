import { useState, useEffect, useRef } from 'react'
import { supabase } from '../lib/supabase'
import { Send, MessageSquare, Building2 } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'

export default function SupportInbox() {
  const [threads, setThreads] = useState([])
  const [selected, setSelected] = useState(null)
  const [messages, setMessages] = useState([])
  const [reply, setReply] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)
  const selectedRef = useRef(null)

  async function loadThreads() {
    const { data } = await supabase
      .from('support_messages')
      .select('company_id, sender_role, content, created_at, read_by_admin, companies(name)')
      .order('created_at', { ascending: false })
    if (!data) return
    const map = {}
    for (const msg of data) {
      if (!map[msg.company_id]) {
        map[msg.company_id] = {
          company_id: msg.company_id,
          company_name: msg.companies?.name || 'Unknown Company',
          last_message: msg.content,
          last_at: msg.created_at,
          unread: 0,
        }
      }
      if (!msg.read_by_admin && msg.sender_role === 'user') {
        map[msg.company_id].unread++
      }
    }
    setThreads(Object.values(map))
  }

  async function loadMessages(cid) {
    const { data } = await supabase.from('support_messages')
      .select('*').eq('company_id', cid).order('created_at', { ascending: true })
    setMessages(data || [])
    setTimeout(() => bottomRef.current?.scrollIntoView(), 50)
    // mark user messages as read
    await supabase.from('support_messages')
      .update({ read_by_admin: true })
      .eq('company_id', cid).eq('sender_role', 'user').eq('read_by_admin', false)
    loadThreads()
  }

  useEffect(() => {
    loadThreads()
    const channel = supabase.channel('support_inbox_admin')
      .on('postgres_changes', { event: 'INSERT', schema: 'public', table: 'support_messages' },
        payload => {
          const cid = payload.new.company_id
          if (selectedRef.current === cid) {
            setMessages(prev =>
              prev.find(m => m.id === payload.new.id) ? prev : [...prev, payload.new]
            )
            bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
            // auto-mark as read if we're viewing this thread
            supabase.from('support_messages')
              .update({ read_by_admin: true }).eq('id', payload.new.id)
          }
          loadThreads()
        })
      .subscribe()
    return () => supabase.removeChannel(channel)
  }, [])

  async function handleSelect(cid) {
    setSelected(cid)
    selectedRef.current = cid
    setMessages([])
    await loadMessages(cid)
  }

  async function sendReply(e) {
    e.preventDefault()
    if (!reply.trim() || !selected || loading) return
    setLoading(true)
    const content = reply.trim()
    setReply('')
    const { data } = await supabase.from('support_messages')
      .insert({ company_id: selected, sender_role: 'admin', content })
      .select().single()
    if (data) {
      setMessages(prev => prev.find(m => m.id === data.id) ? prev : [...prev, data])
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
    setLoading(false)
  }

  const selectedThread = threads.find(t => t.company_id === selected)

  return (
    <div className="h-full flex overflow-hidden">

      {/* Thread list */}
      <div className="w-72 border-r border-gray-200 flex flex-col bg-white flex-shrink-0">
        <div className="px-5 py-5 border-b border-gray-100">
          <h1 className="text-sm font-semibold text-gray-900">Support Inbox</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            {threads.length} conversation{threads.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="flex-1 overflow-y-auto divide-y divide-gray-50">
          {threads.length === 0 && (
            <div className="text-center py-16">
              <MessageSquare className="w-8 h-8 text-gray-200 mx-auto mb-2" />
              <p className="text-xs text-gray-400">No messages yet</p>
            </div>
          )}
          {threads.map(t => (
            <button
              key={t.company_id}
              onClick={() => handleSelect(t.company_id)}
              className={`w-full text-left px-5 py-4 hover:bg-gray-50 transition-colors ${
                selected === t.company_id ? 'bg-accent/5 border-l-2 border-l-accent' : ''
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-900 truncate pr-2">{t.company_name}</span>
                {t.unread > 0 && (
                  <span className="min-w-[20px] h-5 bg-accent text-white text-[10px] rounded-full flex items-center justify-center flex-shrink-0 px-1 font-semibold">
                    {t.unread}
                  </span>
                )}
              </div>
              <p className="text-xs text-gray-400 truncate mb-0.5">{t.last_message}</p>
              <p className="text-xs text-gray-300">
                {formatDistanceToNow(new Date(t.last_at), { addSuffix: true })}
              </p>
            </button>
          ))}
        </div>
      </div>

      {/* Conversation */}
      {selected ? (
        <div className="flex-1 flex flex-col min-h-0">
          <div className="px-6 py-4 border-b border-gray-200 bg-white flex items-center gap-3 flex-shrink-0">
            <Building2 className="w-4 h-4 text-gray-400" />
            <span className="text-sm font-semibold text-gray-900">{selectedThread?.company_name}</span>
          </div>

          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-3 bg-gray-50">
            {messages.map(msg => (
              <div key={msg.id} className={`flex ${msg.sender_role === 'admin' ? 'justify-end' : 'justify-start'}`}>
                <div>
                  {msg.sender_role === 'user' && (
                    <p className="text-xs text-gray-400 mb-1 ml-1">{selectedThread?.company_name}</p>
                  )}
                  <div className={`max-w-sm px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                    msg.sender_role === 'admin'
                      ? 'bg-accent text-white rounded-br-sm'
                      : 'bg-white border border-gray-200 text-gray-800 rounded-bl-sm shadow-sm'
                  }`}>
                    {msg.content}
                  </div>
                  <p className={`text-xs text-gray-300 mt-1 ${msg.sender_role === 'admin' ? 'text-right' : ''}`}>
                    {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          <form onSubmit={sendReply} className="px-6 py-4 bg-white border-t border-gray-200 flex gap-3 flex-shrink-0">
            <input
              value={reply}
              onChange={e => setReply(e.target.value)}
              placeholder={`Reply to ${selectedThread?.company_name}…`}
              className="flex-1 px-4 py-2 text-sm border border-gray-200 rounded-full outline-none focus:border-accent transition-colors"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={!reply.trim() || loading}
              className="w-9 h-9 bg-accent text-white rounded-full flex items-center justify-center hover:bg-accent/90 disabled:opacity-40 transition-colors flex-shrink-0"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center bg-gray-50">
          <div className="text-center">
            <MessageSquare className="w-10 h-10 text-gray-200 mx-auto mb-3" />
            <p className="text-sm text-gray-400">Select a conversation</p>
          </div>
        </div>
      )}
    </div>
  )
}
