import { useState, useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { X, MessageSquare, ExternalLink } from 'lucide-react'

const TOPICS = [
  'Twilio phone number setup',
  'Deepgram API key',
  'ElevenLabs API key',
  'OpenAI API key',
  'Other question',
]

export default function HelpModal({ onClose }) {
  const [topic, setTopic] = useState('')
  const [message, setMessage] = useState('')
  const [userEmail, setUserEmail] = useState('')
  const [companyName, setCompanyName] = useState('')

  useEffect(() => {
    async function load() {
      const { data: { user } } = await supabase.auth.getUser()
      if (!user) return
      setUserEmail(user.email)
      const { data: userData } = await supabase.from('users').select('company_id').eq('id', user.id).single()
      if (userData?.company_id) {
        const { data: company } = await supabase.from('companies').select('name').eq('id', userData.company_id).single()
        if (company?.name) setCompanyName(company.name)
      }
    }
    load()
  }, [])

  function handleSend() {
    const lines = [
      'Hi, I need assistance with my NexaDesk setup.',
      '',
      topic    ? `Topic: ${topic}`       : null,
      message  ? `Message: ${message}`   : null,
      '',
      `Account: ${userEmail}`,
      companyName ? `Company: ${companyName}` : null,
    ].filter(l => l !== null)

    const text = lines.join('\n').trim()
    window.open(`https://wa.me/923312228870?text=${encodeURIComponent(text)}`, '_blank')
    onClose()
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md" onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="flex items-center justify-between px-6 pt-6 pb-4 border-b border-gray-100">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">Get Assistance</h2>
            <p className="text-sm text-gray-500 mt-0.5">We'll help you get set up — chat on WhatsApp</p>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-5">

          {/* Topic chips */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">What do you need help with?</p>
            <div className="flex flex-wrap gap-2">
              {TOPICS.map(t => (
                <button
                  key={t}
                  onClick={() => setTopic(prev => prev === t ? '' : t)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    topic === t
                      ? 'bg-accent text-white border-accent'
                      : 'border-gray-200 text-gray-600 hover:border-accent hover:text-accent'
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>

          {/* Message */}
          <div>
            <label className="text-xs font-semibold text-gray-500 uppercase tracking-wide block mb-2">
              Additional details <span className="font-normal normal-case">(optional)</span>
            </label>
            <textarea
              rows={3}
              value={message}
              onChange={e => setMessage(e.target.value)}
              placeholder="Describe what you're trying to set up..."
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg outline-none focus:border-accent resize-none transition-colors"
            />
          </div>

          {/* Account info notice */}
          <div className="bg-gray-50 rounded-lg px-3 py-2.5 text-xs text-gray-500 leading-relaxed">
            Your email{' '}
            <span className="font-medium text-gray-700">{userEmail || '…'}</span>
            {companyName && (
              <> and company <span className="font-medium text-gray-700">{companyName}</span></>
            )}{' '}
            will be included automatically so we can find your account.
          </div>
        </div>

        {/* CTA */}
        <div className="px-6 pb-6">
          <button
            onClick={handleSend}
            disabled={!topic && !message.trim()}
            className="w-full flex items-center justify-center gap-2 bg-green-500 text-white font-semibold py-3 rounded-xl hover:bg-green-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors text-sm"
          >
            <MessageSquare className="w-4 h-4" />
            Send on WhatsApp
            <ExternalLink className="w-3.5 h-3.5 opacity-70" />
          </button>
        </div>
      </div>
    </div>
  )
}
