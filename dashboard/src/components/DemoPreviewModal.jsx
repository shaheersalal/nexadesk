import { useState, useEffect, useRef, useCallback } from 'react'
import { API_BASE } from '../lib/apiBase'
import { X, ChevronLeft, ChevronRight, Pause, Play, ArrowRight, CheckCircle, TrendingUp, Phone, MessageSquare, Calendar, Globe } from 'lucide-react'

const SLIDE_DURATION = 4000

// ── Slide components ──────────────────────────────────────────────────────────

function Slide1Dashboard() {
  return (
    <div className="h-full flex flex-col p-6 md:p-10" style={{ background: 'linear-gradient(135deg, #0f1f3d 0%, #1a3460 100%)' }}>
      <p className="text-xs font-semibold text-blue-300 uppercase tracking-widest mb-6">Your Command Centre</p>
      <h2 className="text-2xl md:text-4xl font-bold text-white mb-2">Everything at a Glance</h2>
      <p className="text-blue-200 text-sm md:text-base mb-8 max-w-md">Real-time stats, charts, and live activity — all in one clean dashboard your whole team can use.</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {[
          { label: 'Total Leads', value: '248', sub: '+12 today', color: '#e8a87c' },
          { label: 'Avg Score', value: '74', sub: 'out of 100', color: '#60a5fa' },
          { label: 'Appointments', value: '18', sub: 'this week', color: '#34d399' },
          { label: 'Conversations', value: '1,342', sub: 'all time', color: '#a78bfa' },
        ].map(s => (
          <div key={s.label} style={{ background: 'rgba(255,255,255,0.08)', borderRadius: 12, padding: '16px 14px' }}>
            <p className="text-xl md:text-2xl font-bold" style={{ color: s.color }}>{s.value}</p>
            <p className="text-xs text-white/70 mt-1">{s.label}</p>
            <p className="text-xs mt-0.5" style={{ color: s.color, opacity: 0.8 }}>{s.sub}</p>
          </div>
        ))}
      </div>
      <div style={{ background: 'rgba(255,255,255,0.06)', borderRadius: 12, padding: 16, flex: 1 }}>
        <p className="text-xs text-white/50 mb-3">Leads by Status</p>
        <div className="flex items-end gap-2 h-16">
          {[
            { label: 'New', h: '40%', color: '#60a5fa' },
            { label: 'Contacted', h: '75%', color: '#e8a87c' },
            { label: 'Qualified', h: '55%', color: '#34d399' },
            { label: 'Closed', h: '30%', color: '#a78bfa' },
          ].map(b => (
            <div key={b.label} className="flex-1 flex flex-col items-center gap-1">
              <div style={{ width: '100%', height: b.h, background: b.color, borderRadius: '4px 4px 0 0', opacity: 0.85 }} />
              <p className="text-xs text-white/40">{b.label}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Slide2Leads() {
  const cols = [
    { title: 'New', color: '#60a5fa', bg: 'rgba(96,165,250,0.1)', leads: [
      { name: 'James Mitchell', tag: 'Buy · 3BR', score: 82 },
      { name: 'Sarah Al-Rashid', tag: 'Invest', score: 91 },
      { name: 'Tom Bradley', tag: 'Rent', score: 58 },
    ]},
    { title: 'Contacted', color: '#e8a87c', bg: 'rgba(232,168,124,0.1)', leads: [
      { name: 'Emma Rodriguez', tag: 'Buy · 2BR', score: 74 },
      { name: 'Khalid Hassan', tag: 'Buy · Villa', score: 88 },
    ]},
    { title: 'Qualified', color: '#34d399', bg: 'rgba(52,211,153,0.1)', leads: [
      { name: 'Priya Sharma', tag: 'Invest · Off-plan', score: 95 },
      { name: 'David Chen', tag: 'Buy · 4BR', score: 79 },
    ]},
  ]
  return (
    <div className="h-full flex flex-col p-6 md:p-10" style={{ background: 'linear-gradient(135deg, #0a0a1a 0%, #111827 100%)' }}>
      <p className="text-xs font-semibold text-purple-300 uppercase tracking-widest mb-2">Lead Pipeline</p>
      <h2 className="text-2xl md:text-4xl font-bold text-white mb-2">Every Lead, Scored & Ranked</h2>
      <p className="text-gray-400 text-sm md:text-base mb-6">AI scores each lead 0–100 based on intent, budget match, and engagement. Your best prospects surface instantly.</p>
      <div className="grid grid-cols-3 gap-3 flex-1">
        {cols.map(col => (
          <div key={col.title} style={{ background: col.bg, borderRadius: 12, padding: 12, border: `1px solid ${col.color}22` }}>
            <div className="flex items-center gap-2 mb-3">
              <span style={{ width: 8, height: 8, borderRadius: 4, background: col.color, display: 'inline-block' }} />
              <span className="text-xs font-semibold" style={{ color: col.color }}>{col.title}</span>
            </div>
            <div className="flex flex-col gap-2">
              {col.leads.map(l => (
                <div key={l.name} style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 8, padding: '10px 12px' }}>
                  <p className="text-sm font-medium text-white truncate">{l.name}</p>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs text-gray-400">{l.tag}</span>
                    <span className="text-xs font-bold" style={{ color: col.color }}>{l.score}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Slide3Transcript() {
  const messages = [
    { role: 'ai', text: "Hi! I'm Nexa, your AI assistant at Prestige Properties. How can I help you today?" },
    { role: 'client', text: "I'm looking for a 2-bedroom apartment in Dubai Marina, budget around AED 1.5M." },
    { role: 'ai', text: "Great choice — Marina is very popular right now. We have 3 listings in that range. Are you looking to move in soon, or is this an investment?" },
    { role: 'client', text: "Looking to move in within 3 months." },
    { role: 'ai', text: "Perfect. Can I get your name and number so our agent can schedule a viewing for you? We have availability this weekend." },
    { role: 'client', text: "Sure, I'm James. +971 55 123 4567." },
    { role: 'ai', text: "Thank you, James! I've flagged this for our agent. You'll receive a call within 2 hours. Is morning or afternoon better for you?" },
  ]
  return (
    <div className="h-full flex flex-col p-6 md:p-10" style={{ background: 'linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)' }}>
      <p className="text-xs font-semibold text-teal-300 uppercase tracking-widest mb-2">Call Transcripts</p>
      <h2 className="text-2xl md:text-4xl font-bold text-white mb-2">Full Conversation Records</h2>
      <p className="text-teal-100/70 text-sm md:text-base mb-4">Every AI conversation is logged, searchable, and linked to the lead — voice and chat.</p>
      <div className="flex-1 overflow-hidden flex flex-col gap-2 justify-end">
        {messages.slice(-5).map((m, i) => (
          <div key={i} className={`flex ${m.role === 'client' ? 'justify-end' : 'justify-start'}`}>
            <div style={{
              background: m.role === 'ai' ? 'rgba(255,255,255,0.1)' : 'rgba(20,184,166,0.3)',
              borderRadius: m.role === 'ai' ? '4px 16px 16px 16px' : '16px 4px 16px 16px',
              padding: '8px 14px',
              maxWidth: '72%',
            }}>
              <p className="text-xs font-semibold mb-0.5" style={{ color: m.role === 'ai' ? '#5eead4' : '#99f6e4' }}>
                {m.role === 'ai' ? 'Nexa AI' : 'James Mitchell'}
              </p>
              <p className="text-sm text-white/90 leading-relaxed">{m.text}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Slide4Multilingual() {
  const langs = [
    { flag: '🇺🇸', lang: 'English', q: 'I need a 3-bed villa in Jumeirah.', a: "Great choice! Jumeirah villas start from AED 5M. What's your timeline?" },
    { flag: '🇪🇸', lang: 'Español', q: 'Busco un apartamento en Dubai Marina.', a: '¡Perfecto! Tenemos opciones desde AED 900K en Marina. ¿Cuándo planea mudarse?' },
    { flag: '🇫🇷', lang: 'Français', q: "Je cherche un investissement à Dubai.", a: 'Excellent choix! Le rendement moyen est de 7%. Quel est votre budget?' },
    { flag: '🇸🇦', lang: 'العربية', q: 'أبحث عن شقة في داون تاون دبي.', a: 'ممتاز! لدينا شقق في داون تاون من مليون و٢٠٠ ألف درهم. متى تريد الانتقال؟' },
  ]
  return (
    <div className="h-full flex flex-col p-6 md:p-10" style={{ background: 'linear-gradient(135deg, #1a0533 0%, #2d1b69 100%)' }}>
      <p className="text-xs font-semibold text-violet-300 uppercase tracking-widest mb-2">Multilingual AI</p>
      <h2 className="text-2xl md:text-4xl font-bold text-white mb-2">Speaks Your Clients' Language</h2>
      <p className="text-violet-200/70 text-sm md:text-base mb-6">Nexa auto-detects your client's language and replies in kind — from Arabic to Spanish to Urdu, no setup needed.</p>
      <div className="grid grid-cols-2 gap-3 flex-1">
        {langs.map(l => (
          <div key={l.lang} style={{ background: 'rgba(255,255,255,0.07)', borderRadius: 12, padding: 14, border: '1px solid rgba(255,255,255,0.1)' }}>
            <p className="text-lg mb-1">{l.flag} <span className="text-xs font-semibold text-violet-300 ml-1">{l.lang}</span></p>
            <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 8, padding: '6px 10px', marginBottom: 6 }}>
              <p className="text-xs text-white/60" style={{ direction: l.lang === 'العربية' ? 'rtl' : 'ltr' }}>{l.q}</p>
            </div>
            <div style={{ background: 'rgba(139,92,246,0.2)', borderRadius: 8, padding: '6px 10px' }}>
              <p className="text-xs text-violet-100" style={{ direction: l.lang === 'العربية' ? 'rtl' : 'ltr' }}>{l.a}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Slide5Appointments() {
  const appts = [
    { name: 'James Mitchell', property: 'Marina Heights — Unit 2204', time: 'Today · 2:00 PM', status: 'confirmed', avatar: 'JM' },
    { name: 'Emma Rodriguez', property: 'Downtown Boulevard — 1BR', time: 'Tomorrow · 10:30 AM', status: 'confirmed', avatar: 'ER' },
    { name: 'Khalid Hassan', property: 'Palm Jumeirah — Villa 7', time: 'Thu · 3:00 PM', status: 'pending', avatar: 'KH' },
    { name: 'Priya Sharma', property: 'Business Bay — Off-plan Apt', time: 'Fri · 11:00 AM', status: 'confirmed', avatar: 'PS' },
    { name: 'David Chen', property: 'JBR — Beachfront 2BR', time: 'Sat · 1:00 PM', status: 'confirmed', avatar: 'DC' },
  ]
  return (
    <div className="h-full flex flex-col p-6 md:p-10" style={{ background: 'linear-gradient(135deg, #0d1f0d 0%, #1a2e1a 100%)' }}>
      <p className="text-xs font-semibold text-green-400 uppercase tracking-widest mb-2">Appointments</p>
      <h2 className="text-2xl md:text-4xl font-bold text-white mb-2">Viewings, Auto-Booked</h2>
      <p className="text-green-200/70 text-sm md:text-base mb-6">Nexa books viewings directly into your calendar without you lifting a finger.</p>
      <div className="flex flex-col gap-2 flex-1 justify-center">
        {appts.map(a => (
          <div key={a.name} style={{ background: 'rgba(255,255,255,0.06)', borderRadius: 10, padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: 18, background: 'rgba(52,211,153,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              <span className="text-xs font-bold text-green-300">{a.avatar}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white">{a.name}</p>
              <p className="text-xs text-gray-400 truncate">{a.property}</p>
            </div>
            <div className="text-right flex-shrink-0">
              <p className="text-xs text-white/80">{a.time}</p>
              <span style={{
                fontSize: 10, fontWeight: 600,
                color: a.status === 'confirmed' ? '#34d399' : '#fbbf24',
                background: a.status === 'confirmed' ? 'rgba(52,211,153,0.15)' : 'rgba(251,191,36,0.15)',
                borderRadius: 4, padding: '2px 7px', display: 'inline-block', marginTop: 2,
              }}>
                {a.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

const SLIDES = [
  { component: Slide1Dashboard, title: 'Live Dashboard', desc: 'Real-time metrics and AI activity at a glance' },
  { component: Slide2Leads, title: 'Lead Pipeline', desc: 'Every enquiry scored, ranked, and ready to act on' },
  { component: Slide3Transcript, title: 'Full Transcripts', desc: 'Every conversation logged automatically' },
  { component: Slide4Multilingual, title: 'Multilingual AI', desc: "Speaks your client's language — automatically" },
  { component: Slide5Appointments, title: 'Auto Appointments', desc: 'Viewings booked without you lifting a finger' },
]

// ── Form ──────────────────────────────────────────────────────────────────────

const COUNTRIES = ['United States', 'United Kingdom', 'UAE', 'Saudi Arabia', 'Qatar', 'Kuwait', 'Bahrain', 'Oman', 'Canada', 'Australia', 'Other']
const CALL_RANGES = ['Under 100', '100–300', '300–500', '500–1000', '1000+']

const PENDING_LEAD_KEY = 'nexadesk_pending_lead'

const RECAPTCHA_SITE_KEY = import.meta.env.VITE_RECAPTCHA_SITE_KEY || ''

async function getRecaptchaToken() {
  if (!RECAPTCHA_SITE_KEY || !window.grecaptcha) return null
  return window.grecaptcha.execute(RECAPTCHA_SITE_KEY, { action: 'demo_submit' })
}

function DemoForm({ onSuccess, onBack }) {
  const [form, setForm] = useState({ name: '', email: '', agency: '', phone: '', country: '', monthly_calls: '' })
  const [hp, setHp] = useState('')  // honeypot — should always be empty for real users
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const set = (k) => (e) => setForm(f => ({ ...f, [k]: e.target.value }))

  async function submit(e) {
    e.preventDefault()
    // Honeypot — bots fill hidden fields, humans never see it
    if (hp) return
    if (!form.name || !form.email || !form.agency || !form.phone || !form.country || !form.monthly_calls) {
      setError('Please fill in all fields.')
      return
    }
    setLoading(true)
    setError('')

    // Persist before any network call — if both the backend and the fallback
    // fail, the submission isn't silently lost.
    localStorage.setItem(PENDING_LEAD_KEY, JSON.stringify({ ...form, submitted_at: new Date().toISOString() }))

    // Attach any discount the user confirmed in the pricing chat
    const discountRaw = sessionStorage.getItem('nexadesk_confirmed_discount')
    const discount = discountRaw ? JSON.parse(discountRaw) : null

    const recaptcha_token = await getRecaptchaToken()

    let delivered = false
    try {
      const res = await fetch(`${API_BASE}/book-demo`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, ...(discount || {}), recaptcha_token }),
        signal: AbortSignal.timeout(5000),
      })
      if (res.ok) delivered = true
    } catch {
      // backend unreachable or timed out — fall through to the Vercel fallback
    }

    if (!delivered) {
      try {
        const fallbackRes = await fetch('/api/capture-lead', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(form),
          signal: AbortSignal.timeout(5000),
        })
        if (fallbackRes.ok) delivered = true
      } catch {
        // both paths failed
      }
    }

    setLoading(false)

    if (delivered) {
      localStorage.removeItem(PENDING_LEAD_KEY)
      onSuccess()
    } else {
      setError("That didn't go through — please try again in a few minutes.")
    }
  }

  const inputClass = 'w-full rounded-xl border border-white/10 bg-white/5 text-white placeholder-white/30 px-4 py-3 text-sm focus:outline-none focus:border-white/30 focus:bg-white/8 transition-all'
  const labelClass = 'block text-xs font-semibold text-white/50 uppercase tracking-wider mb-1.5'

  return (
    <div className="h-full overflow-y-auto flex flex-col items-center p-6 md:p-8 pt-6" style={{ background: 'linear-gradient(135deg, #0f1f3d 0%, #1a1a2e 100%)' }}>
      <div className="w-full max-w-md flex flex-col flex-1 justify-center min-h-max py-4">
      <button onClick={onBack} className="self-start flex items-center gap-1.5 text-white/40 hover:text-white/70 text-sm mb-5 transition-colors">
        <ChevronLeft className="w-4 h-4" /> Back to preview
      </button>
      <div className="w-full max-w-md">
        <h2 className="text-2xl md:text-3xl font-bold text-white mb-1">Get Early Access</h2>
        <p className="text-white/50 text-sm mb-6">We'll send your payment link within 1 hour and set everything up for you.</p>

        <form onSubmit={submit} className="flex flex-col gap-4">
          {/* Honeypot — invisible to humans, bots fill it → silent drop */}
          <div style={{ position: 'absolute', left: '-9999px', opacity: 0, height: 0, overflow: 'hidden' }} aria-hidden="true">
            <input tabIndex={-1} autoComplete="off" value={hp} onChange={e => setHp(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Your Name</label>
              <input className={inputClass} placeholder="John Smith" value={form.name} onChange={set('name')} />
            </div>
            <div>
              <label className={labelClass}>Agency Name</label>
              <input className={inputClass} placeholder="Prestige Realty" value={form.agency} onChange={set('agency')} />
            </div>
          </div>
          <div>
            <label className={labelClass}>Email</label>
            <input className={inputClass} type="email" placeholder="john@agency.com" value={form.email} onChange={set('email')} />
          </div>
          <div>
            <label className={labelClass}>Phone / WhatsApp</label>
            <input className={inputClass} placeholder="+1 555 000 0000" value={form.phone} onChange={set('phone')} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelClass}>Country</label>
              <select className={inputClass + ' appearance-none cursor-pointer'} value={form.country} onChange={set('country')}>
                <option value="" disabled style={{ background: '#1a1a2e' }}>Select…</option>
                {COUNTRIES.map(c => <option key={c} value={c} style={{ background: '#1a1a2e' }}>{c}</option>)}
              </select>
            </div>
            <div>
              <label className={labelClass}>Monthly Calls</label>
              <select className={inputClass + ' appearance-none cursor-pointer'} value={form.monthly_calls} onChange={set('monthly_calls')}>
                <option value="" disabled style={{ background: '#1a1a2e' }}>Select…</option>
                {CALL_RANGES.map(r => <option key={r} value={r} style={{ background: '#1a1a2e' }}>{r}</option>)}
              </select>
            </div>
          </div>

          {error && <p className="text-red-400 text-xs">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full flex items-center justify-center gap-2 font-semibold py-3.5 rounded-xl text-sm transition-all"
            style={{ background: loading ? 'rgba(232,168,124,0.5)' : '#e8a87c', color: '#1a1a2e', cursor: loading ? 'not-allowed' : 'pointer' }}
          >
            {loading ? 'Sending…' : <><span>Request Access</span> <ArrowRight className="w-4 h-4" /></>}
          </button>
        </form>
      </div>
      </div>
    </div>
  )
}

// ── Success screen ─────────────────────────────────────────────────────────────

function SuccessScreen() {
  return (
    <div className="h-full flex flex-col items-center justify-center p-10 text-center" style={{ background: 'linear-gradient(135deg, #0f1f3d 0%, #1a1a2e 100%)' }}>
      <div className="w-16 h-16 rounded-full flex items-center justify-center mb-6" style={{ background: 'rgba(52,211,153,0.2)' }}>
        <CheckCircle className="w-8 h-8 text-green-400" />
      </div>
      <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">You're on the List</h2>
      <p className="text-white/60 text-base max-w-sm mb-2">
        Your payment link is on its way. Expect an email within <strong className="text-white">1 hour</strong>.
      </p>
      <p className="text-white/40 text-sm">
        Don't see it? Check your spam folder just in case.
      </p>
    </div>
  )
}

// ── Main modal ─────────────────────────────────────────────────────────────────

export default function DemoPreviewModal({ onClose }) {
  const [slide, setSlide] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const [progress, setProgress] = useState(0)
  const [slideComplete, setSlideComplete] = useState(false)
  const [stage, setStage] = useState('slides') // 'slides' | 'form' | 'success'
  const progressRef = useRef(null)
  const startRef = useRef(null)
  const pausedAtRef = useRef(null)

  const goToSlide = useCallback((idx) => {
    setSlide(idx)
    setProgress(0)
    setSlideComplete(false)
    startRef.current = null
    pausedAtRef.current = null
  }, [])

  const next = useCallback(() => {
    if (slide < SLIDES.length - 1) goToSlide(slide + 1)
  }, [slide, goToSlide])

  const prev = useCallback(() => {
    if (slide > 0) goToSlide(slide - 1)
  }, [slide, goToSlide])

  useEffect(() => {
    if (stage !== 'slides') return
    if (slideComplete) return

    const animate = (timestamp) => {
      if (isPaused) {
        pausedAtRef.current = pausedAtRef.current ?? (timestamp - (startRef.current ?? timestamp))
        progressRef.current = requestAnimationFrame(animate)
        return
      }
      if (!startRef.current) {
        startRef.current = timestamp - (pausedAtRef.current ?? 0)
        pausedAtRef.current = null
      }
      const elapsed = timestamp - startRef.current
      const pct = Math.min((elapsed / SLIDE_DURATION) * 100, 100)
      setProgress(pct)
      if (pct < 100) {
        progressRef.current = requestAnimationFrame(animate)
      } else {
        if (slide === SLIDES.length - 1) {
          setSlideComplete(true)
        } else {
          next()
        }
      }
    }

    progressRef.current = requestAnimationFrame(animate)
    return () => {
      if (progressRef.current) cancelAnimationFrame(progressRef.current)
    }
  }, [slide, isPaused, slideComplete, stage, next])

  // Keyboard nav
  useEffect(() => {
    const handler = (e) => {
      if (e.key === 'ArrowRight') next()
      if (e.key === 'ArrowLeft') prev()
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [next, prev, onClose])

  const SlideComp = SLIDES[slide]?.component

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-0 md:p-6"
      style={{ background: 'rgba(0,0,0,0.85)', backdropFilter: 'blur(8px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose() }}
    >
      <div
        className="relative w-full h-full md:h-auto md:max-w-3xl md:rounded-2xl overflow-hidden"
        style={{ aspectRatio: window.innerWidth >= 768 ? '16/9' : undefined, maxHeight: '95vh', background: '#0f1f3d' }}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 z-30 w-8 h-8 rounded-full flex items-center justify-center text-white/60 hover:text-white hover:bg-white/10 transition-all"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Back arrow (visible in form stage) */}
        {stage === 'form' && (
          <button
            onClick={() => setStage('slides')}
            className="absolute top-4 left-4 z-30 w-8 h-8 rounded-full flex items-center justify-center text-white/60 hover:text-white hover:bg-white/10 transition-all"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
        )}

        {/* Slide content */}
        <div className="w-full h-full" style={{ minHeight: 400 }}>
          {stage === 'slides' && SlideComp && (
            <div className="relative w-full h-full">
              {/* Tap zones — left third goes back, right two-thirds goes forward/completes */}
              {!slideComplete && (
                <>
                  <div className="absolute inset-y-0 left-0 z-10 cursor-pointer select-none"
                    style={{ width: '33%' }}
                    onClick={(e) => { e.stopPropagation(); prev() }}
                  />
                  <div className="absolute inset-y-0 right-0 z-10 cursor-pointer select-none"
                    style={{ width: '67%' }}
                    onClick={(e) => {
                      e.stopPropagation()
                      if (slide === SLIDES.length - 1) setSlideComplete(true)
                      else next()
                    }}
                  />
                </>
              )}
              <SlideComp />

              {/* Last-slide overlay + proceed button */}
              {slideComplete && (
                <div className="absolute inset-0 flex flex-col items-center justify-center" style={{ background: 'rgba(0,0,0,0.65)', animation: 'fadeIn 0.5s ease' }}>
                  <p className="text-white/60 text-sm mb-4">Ready to automate your agency?</p>
                  <button
                    onClick={() => setStage('form')}
                    className="flex items-center gap-2 font-semibold px-8 py-4 rounded-2xl text-base transition-all hover:scale-105"
                    style={{ background: '#e8a87c', color: '#1a1a2e', boxShadow: '0 8px 32px rgba(232,168,124,0.4)' }}
                  >
                    Get Started <ArrowRight className="w-5 h-5" />
                  </button>
                </div>
              )}

              {/* Progress bar */}
              {!slideComplete && (
                <div className="absolute top-0 left-0 right-0 flex gap-1 p-3 z-20">
                  {SLIDES.map((_, i) => (
                    <div key={i} className="flex-1 h-0.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.2)' }}>
                      <div
                        style={{
                          height: '100%',
                          width: i < slide ? '100%' : i === slide ? `${progress}%` : '0%',
                          background: 'white',
                          transition: i === slide ? 'none' : undefined,
                        }}
                      />
                    </div>
                  ))}
                </div>
              )}

              {/* Bottom controls */}
              {!slideComplete && (
                <div className="absolute bottom-0 left-0 right-0 flex items-center justify-between px-4 pb-4 pt-8 z-20"
                  style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.5), transparent)' }}>
                  <div className="flex items-center gap-2">
                    <button onClick={prev} disabled={slide === 0}
                      className="w-7 h-7 rounded-full flex items-center justify-center text-white/60 hover:text-white disabled:opacity-30 transition-all"
                      style={{ background: 'rgba(255,255,255,0.1)' }}>
                      <ChevronLeft className="w-4 h-4" />
                    </button>
                    <button onClick={next} disabled={slide === SLIDES.length - 1}
                      className="w-7 h-7 rounded-full flex items-center justify-center text-white/60 hover:text-white disabled:opacity-30 transition-all"
                      style={{ background: 'rgba(255,255,255,0.1)' }}>
                      <ChevronRight className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => setIsPaused(p => !p)}
                      className="w-7 h-7 rounded-full flex items-center justify-center text-white/60 hover:text-white transition-all"
                      style={{ background: 'rgba(255,255,255,0.1)' }}>
                      {isPaused ? <Play className="w-3.5 h-3.5" /> : <Pause className="w-3.5 h-3.5" />}
                    </button>
                  </div>

                  {/* Dot indicators */}
                  <div className="flex gap-1.5">
                    {SLIDES.map((_, i) => (
                      <button key={i} onClick={() => goToSlide(i)}
                        style={{
                          width: i === slide ? 20 : 6,
                          height: 6,
                          borderRadius: 3,
                          background: i === slide ? 'white' : 'rgba(255,255,255,0.35)',
                          transition: 'all 0.3s ease',
                          border: 'none',
                          cursor: 'pointer',
                          padding: 0,
                        }}
                      />
                    ))}
                  </div>

                  {/* Slide label */}
                  <p className="text-xs text-white/50 hidden md:block">{SLIDES[slide].title}</p>
                </div>
              )}
            </div>
          )}

          {stage === 'form' && (
            <DemoForm onSuccess={() => setStage('success')} onBack={() => setStage('slides')} />
          )}

          {stage === 'success' && <SuccessScreen />}
        </div>
      </div>

      <style>{`
        @keyframes fadeIn { from { opacity: 0 } to { opacity: 1 } }
      `}</style>
    </div>
  )
}
