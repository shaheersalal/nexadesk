import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../lib/api'
import { ArrowLeft, Phone, Mail, User, MessageSquare, Calendar, Wrench, RefreshCw, Star } from 'lucide-react'
import { format } from 'date-fns'

function badge(status) {
  const map = {
    new: 'bg-gray-100 text-gray-600',
    contacted: 'bg-blue-50 text-blue-600',
    qualified: 'bg-yellow-50 text-yellow-700',
    appointment: 'bg-green-50 text-green-700',
    closed_won: 'bg-emerald-50 text-emerald-700',
    closed_lost: 'bg-red-50 text-red-500',
  }
  return map[status] || 'bg-gray-100 text-gray-600'
}

function requestType(notes) {
  if (!notes) return null
  if (notes.startsWith('[MAINTENANCE]')) return { label: 'Maintenance Request', icon: Wrench, color: 'text-orange-500 bg-orange-50' }
  if (notes.startsWith('[LEASE RENEWAL]')) return { label: 'Lease Renewal', icon: RefreshCw, color: 'text-purple-500 bg-purple-50' }
  return null
}

function ScoreMeter({ score }) {
  const pct = Math.min(100, score)
  const color = pct >= 60 ? 'bg-green-500' : pct >= 30 ? 'bg-yellow-400' : 'bg-gray-300'
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
        <span>Lead Score</span>
        <span className="font-semibold text-gray-800">{score}/100</span>
      </div>
      <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function ScoreBreakdown({ breakdown }) {
  if (!breakdown || Object.keys(breakdown).length === 0) return null
  return (
    <div className="card">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-1.5">
        <Star className="w-3.5 h-3.5" /> Score Breakdown
      </h3>
      <div className="space-y-1.5">
        {Object.entries(breakdown).map(([rule, delta]) => (
          <div key={rule} className="flex items-center justify-between text-xs">
            <span className="text-gray-500 capitalize">{rule.replace(/_/g, ' ')}</span>
            <span className={`font-semibold ${delta > 0 ? 'text-green-600' : 'text-red-400'}`}>
              {delta > 0 ? '+' : ''}{delta}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ConversationTranscript({ conversation }) {
  const transcript = conversation.transcript || []
  const isVoice = conversation.channel === 'voice'

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center gap-2 mb-1">
        {isVoice
          ? <Phone className="w-4 h-4 text-gray-400" />
          : <MessageSquare className="w-4 h-4 text-gray-400" />}
        <span className="text-sm font-semibold text-gray-800 capitalize">
          {isVoice ? 'Voice Call' : 'Chat'} Transcript
        </span>
        {conversation.language && conversation.language !== 'en' && (
          <span className="ml-1 text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full uppercase">
            {conversation.language}
          </span>
        )}
        <span className="text-xs text-gray-400 ml-auto">
          {format(new Date(conversation.started_at), 'MMM d, h:mm a')}
        </span>
      </div>

      {/* Meta */}
      <div className="flex items-center gap-4 mb-4 text-xs text-gray-400">
        {conversation.call_duration && (
          <span>{Math.floor(conversation.call_duration / 60)}m {conversation.call_duration % 60}s</span>
        )}
        {conversation.sentiment && (
          <span className={`capitalize ${conversation.sentiment === 'positive' ? 'text-green-500' : 'text-gray-400'}`}>
            {conversation.sentiment}
          </span>
        )}
      </div>

      {/* Summary */}
      {conversation.summary && (
        <div className="bg-gray-50 rounded-lg px-3 py-2 mb-4 text-xs text-gray-600 leading-relaxed">
          <span className="font-medium text-gray-700">AI Summary: </span>{conversation.summary}
        </div>
      )}

      {/* Messages */}
      <div className="space-y-3 max-h-80 overflow-y-auto pr-1">
        {transcript.map((turn, i) => (
          <div key={i} className={`flex gap-2 ${turn.role === 'user' ? 'justify-start' : 'justify-end'}`}>
            {turn.role === 'user' && (
              <div className="w-6 h-6 rounded-full bg-gray-200 flex items-center justify-center flex-shrink-0 mt-0.5">
                <User className="w-3 h-3 text-gray-500" />
              </div>
            )}
            <div className={`max-w-[75%] px-3 py-2 rounded-2xl text-sm leading-relaxed ${
              turn.role === 'user'
                ? 'bg-gray-100 text-gray-800 rounded-tl-sm'
                : 'bg-navy-600 text-white rounded-tr-sm'
            }`}>
              {turn.content}
            </div>
          </div>
        ))}
        {transcript.length === 0 && (
          <p className="text-sm text-gray-400 text-center py-6">No transcript available</p>
        )}
      </div>
    </div>
  )
}

export default function LeadDetail() {
  const { id } = useParams()
  const [lead, setLead] = useState(null)

  useEffect(() => {
    api.getLead(id).then(setLead).catch(console.error)
  }, [id])

  if (!lead) {
    return (
      <div className="p-8 flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  const reqType = requestType(lead.notes)

  return (
    <div className="p-8 max-w-5xl">
      <Link to="/leads" className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 mb-6">
        <ArrowLeft className="w-4 h-4" /> Back to leads
      </Link>

      <div className="grid grid-cols-3 gap-6">
        {/* Left column */}
        <div className="col-span-1 space-y-4">
          <div className="card">
            {/* Request type badge */}
            {reqType && (
              <div className={`inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full mb-3 ${reqType.color}`}>
                <reqType.icon className="w-3 h-3" />
                {reqType.label}
              </div>
            )}

            <div className="w-12 h-12 rounded-full bg-accent/10 flex items-center justify-center mb-3">
              <User className="w-6 h-6 text-accent" />
            </div>
            <h1 className="text-lg font-semibold text-gray-900">{lead.name || 'Unknown'}</h1>
            <div className="flex items-center gap-2 mt-1 mb-4">
              <span className="text-xs text-gray-400 capitalize">{lead.source} ·</span>
              <span className={`text-xs font-medium px-2 py-0.5 rounded-full capitalize ${badge(lead.status)}`}>
                {lead.status.replace('_', ' ')}
              </span>
              {lead.language && lead.language !== 'en' && (
                <span className="text-xs bg-blue-50 text-blue-500 px-2 py-0.5 rounded-full uppercase">{lead.language}</span>
              )}
            </div>

            {lead.phone && (
              <div className="flex items-center gap-2 text-sm text-gray-600 mb-2">
                <Phone className="w-4 h-4 text-gray-400" />{lead.phone}
              </div>
            )}
            {lead.email && (
              <div className="flex items-center gap-2 text-sm text-gray-600 mb-4">
                <Mail className="w-4 h-4 text-gray-400" />{lead.email}
              </div>
            )}

            {!reqType && <ScoreMeter score={lead.score || 0} />}
          </div>

          {lead.notes && (
            <div className="card">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">AI Notes</h3>
              <p className="text-sm text-gray-600 leading-relaxed">
                {lead.notes.replace(/^\[.*?\]\s*/, '')}
              </p>
            </div>
          )}

          {!reqType && <ScoreBreakdown breakdown={lead.score_breakdown} />}

          {lead.appointments?.length > 0 && (
            <div className="card">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Appointments</h3>
              {lead.appointments.map((appt) => (
                <div key={appt.id} className="flex items-start gap-2 text-sm text-gray-600 mb-3 last:mb-0">
                  <Calendar className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-medium">{format(new Date(appt.datetime), 'EEE, MMM d · h:mm a')}</p>
                    <p className="text-xs text-gray-400 capitalize">{appt.type} · {appt.status}</p>
                    {appt.notes && <p className="text-xs text-gray-400 mt-0.5">{appt.notes}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: conversations */}
        <div className="col-span-2 space-y-4">
          <h2 className="text-sm font-semibold text-gray-700">
            {reqType ? 'AI-Handled Request' : 'Conversation History'}
          </h2>
          {lead.conversations?.length > 0
            ? lead.conversations.map((conv) => (
                <ConversationTranscript key={conv.id} conversation={conv} />
              ))
            : (
              <div className="card text-center py-12">
                <MessageSquare className="w-8 h-8 text-gray-200 mx-auto mb-3" />
                <p className="text-sm text-gray-400">No conversations yet</p>
              </div>
            )}
        </div>
      </div>
    </div>
  )
}
