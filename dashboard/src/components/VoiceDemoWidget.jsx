import { useState, useRef, useCallback } from 'react'
import { Mic, Square, Loader2, Volume2 } from 'lucide-react'

// Calls the real backend (Deepgram -> gpt-4o-mini -> ElevenLabs), the same
// chain the production phone line uses. The previous version posted to the
// standalone Vercel demo app's /api/voice route, which no longer exists.
const API_BASE = import.meta.env.VITE_API_URL || 'https://api.nexadesk.site'

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'ur', label: 'اردو' },
  { code: 'ar', label: 'العربية' },
  { code: 'auto', label: 'Auto' },
]

const MIN_RECORD_MS = 1000

function bestMimeType() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
  return candidates.find(t => MediaRecorder.isTypeSupported(t)) ?? ''
}

export default function VoiceDemoWidget() {
  const [stage, setStage] = useState('idle')   // idle | recording | processing | speaking | error
  const [lang, setLang] = useState('en')
  const [transcript, setTranscript] = useState('')
  const [reply, setReply] = useState('')
  const [errorMsg, setErrorMsg] = useState('')
  const [history, setHistory] = useState([])

  const recorderRef = useRef(null)
  const chunksRef = useRef([])
  const langRef = useRef('en')
  const startedAt = useRef(0)
  const shouldSend = useRef(true)
  const audioRef = useRef(null)

  const showError = (msg) => { setStage('error'); setErrorMsg(msg) }

  const play = (b64) => {
    setStage('speaking')
    if (!audioRef.current) audioRef.current = new Audio()
    audioRef.current.src = `data:audio/mpeg;base64,${b64}`
    audioRef.current.onended = () => setStage('idle')
    audioRef.current.onerror = () => setStage('idle')
    audioRef.current.play().catch(() => setStage('idle'))
  }

  const send = useCallback(async (blob, mime) => {
    setStage('processing')
    try {
      const fd = new FormData()
      fd.append('audio', blob, `audio.${mime.includes('ogg') ? 'ogg' : 'webm'}`)
      fd.append('lang', langRef.current)
      fd.append('history', JSON.stringify(history))

      const res = await fetch(`${API_BASE}/demo/voice`, { method: 'POST', body: fd })
      const data = await res.json().catch(() => ({}))
      if (!res.ok) { showError(data.detail || 'Request failed'); return }

      setTranscript(data.transcript)
      setReply(data.reply)
      setHistory(h => [
        ...h,
        { role: 'user', content: data.historyUser },
        { role: 'assistant', content: data.historyAssistant },
      ])
      if (data.audio) play(data.audio)
      else setStage('idle')   // reply text still shown if TTS is unavailable
    } catch {
      showError('Network error — please try again.')
    }
  }, [history])

  const start = useCallback(async () => {
    chunksRef.current = []
    shouldSend.current = true
    setTranscript(''); setReply(''); setErrorMsg('')

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    } catch {
      showError("Couldn't access the microphone — check browser permissions.")
      return
    }

    const mime = bestMimeType()
    const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : {})
    const actualMime = rec.mimeType || mime || 'audio/webm'
    recorderRef.current = rec

    rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
    rec.onstop = async () => {
      stream.getTracks().forEach(t => t.stop())
      if (!shouldSend.current) return
      await send(new Blob(chunksRef.current, { type: actualMime }), actualMime)
    }

    rec.start(250)
    startedAt.current = Date.now()
    setStage('recording')
  }, [send])

  const stop = useCallback(() => {
    if (Date.now() - startedAt.current < MIN_RECORD_MS) {
      shouldSend.current = false
      recorderRef.current?.stop()
      showError('Hold on a moment longer and try again.')
      return
    }
    recorderRef.current?.stop()
  }, [])

  const onClick = () => {
    if (stage === 'recording') return stop()
    if (stage === 'processing' || stage === 'speaking') return
    start()
  }

  const label = {
    idle: 'Click to talk',
    recording: 'Listening… click to stop',
    processing: 'Thinking…',
    speaking: 'Speaking…',
    error: errorMsg || 'Something went wrong',
  }[stage]

  return (
    <div className="max-w-sm mx-auto">
      <div className="border border-gray-200 rounded-2xl shadow-lg overflow-hidden">
        <div className="flex items-center gap-3 px-4 py-3 bg-navy-600">
          <div className="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-white text-xs font-bold">N</div>
          <div className="flex-1">
            <span className="text-sm font-semibold text-white block leading-tight">Nexa · Voice Demo</span>
            <span className="flex items-center gap-1 text-xs text-green-400">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 inline-block animate-pulse" />
              online
            </span>
          </div>
        </div>

        <div className="p-6 flex flex-col items-center gap-4 bg-white">
          <div className="flex gap-1.5 flex-wrap justify-center">
            {LANGUAGES.map(l => (
              <button
                key={l.code}
                onClick={() => { setLang(l.code); langRef.current = l.code }}
                disabled={stage === 'recording' || stage === 'processing'}
                className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors disabled:opacity-40 ${
                  lang === l.code
                    ? 'bg-accent border-accent text-white'
                    : 'border-gray-200 text-gray-500 hover:border-gray-400'
                }`}
              >
                {l.label}
              </button>
            ))}
          </div>

          <button
            onClick={onClick}
            disabled={stage === 'processing' || stage === 'speaking'}
            className={`w-20 h-20 rounded-full flex items-center justify-center text-white transition-all shadow-lg disabled:opacity-60 ${
              stage === 'recording' ? 'bg-red-500 animate-pulse' : 'bg-accent hover:bg-accent-light'
            }`}
            aria-label={label}
          >
            {stage === 'recording' ? <Square size={26} />
              : stage === 'processing' ? <Loader2 size={26} className="animate-spin" />
              : stage === 'speaking' ? <Volume2 size={26} />
              : <Mic size={26} />}
          </button>

          <p className={`text-sm text-center min-h-[1.25rem] ${stage === 'error' ? 'text-red-500' : 'text-gray-500'}`}>
            {label}
          </p>

          {transcript && stage !== 'error' && (
            <p className="text-xs text-gray-400 italic text-center">“{transcript}”</p>
          )}
          {reply && stage !== 'error' && (
            <p className="text-sm text-gray-700 text-center leading-relaxed bg-gray-50 rounded-lg p-3 w-full">
              {reply}
            </p>
          )}

          {history.length > 0 && (
            <button
              onClick={() => { setHistory([]); setTranscript(''); setReply('') }}
              className="text-xs text-gray-400 hover:text-gray-600 underline"
            >
              Clear conversation
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
