'use client'
import { useState, useRef, useCallback } from 'react'
import { Mic, MicOff, Loader2, Volume2 } from 'lucide-react'

const VERCEL_API = 'https://nexadesk-1j2y.vercel.app'

const LANGUAGES = [
  { code: 'en',   label: 'English'  },
  { code: 'ur',   label: 'اردو'     },
  { code: 'ar',   label: 'العربية'  },
  { code: 'auto', label: 'Auto'     },
]

const MIN_RECORD_MS     = 1500
const ENCODER_WARMUP_MS = 250

function bestMimeType() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
  return candidates.find(t => MediaRecorder.isTypeSupported(t)) ?? ''
}

export default function VoiceDemoWidget() {
  const [stage, setStage]           = useState('idle')   // idle | recording | processing | speaking | error
  const [lang, setLang]             = useState('en')
  const [transcript, setTranscript] = useState('')
  const [replyText, setReplyText]   = useState('')
  const [errorMsg, setErrorMsg]     = useState('')
  const [history, setHistory]       = useState([])

  const recorderRef  = useRef(null)
  const chunksRef    = useRef([])
  const streamRef    = useRef(null)
  const langRef      = useRef('en')
  const startRef     = useRef(0)
  const shouldSend   = useRef(true)
  const audioRef     = useRef(null)

  const handleLangChange = (code) => { setLang(code); langRef.current = code }

  const showError = (msg) => { setStage('error'); setErrorMsg(msg) }

  const playBase64Mp3 = (b64) => {
    setStage('speaking')
    const src = `data:audio/mpeg;base64,${b64}`
    if (!audioRef.current) audioRef.current = new Audio()
    audioRef.current.src = src
    audioRef.current.onended = () => setStage('idle')
    audioRef.current.onerror = () => setStage('idle')
    audioRef.current.play().catch(() => setStage('idle'))
  }

  const sendAudio = useCallback(async (blob, mimeType) => {
    setStage('processing')
    try {
      const fd = new FormData()
      fd.append('audio', blob, `audio.${mimeType.includes('ogg') ? 'ogg' : 'webm'}`)
      fd.append('lang', langRef.current)
      fd.append('history', JSON.stringify(history))

      const res  = await fetch(`${VERCEL_API}/api/voice`, { method: 'POST', body: fd })
      const data = await res.json()

      if (!res.ok || data.error) { showError(data.error || 'Request failed'); return }

      setTranscript(data.transcript)
      setReplyText(data.reply)
      setHistory(h => [
        ...h,
        { role: 'user',      content: data.historyUser      },
        { role: 'assistant', content: data.historyAssistant },
      ])
      playBase64Mp3(data.audio)
    } catch {
      showError('Could not reach demo server — try again.')
    }
  }, [history])

  const stopRecording = useCallback(() => {
    const duration = Date.now() - startRef.current
    if (duration < MIN_RECORD_MS) {
      shouldSend.current = false
      recorderRef.current?.stop()
      showError('Hold the button longer and try again.')
      return
    }
    recorderRef.current?.stop()
  }, [])

  const startRecording = useCallback(async () => {
    chunksRef.current  = []
    shouldSend.current = true
    setTranscript('')
    setReplyText('')
    setErrorMsg('')

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, sampleRate: 48000, channelCount: 1 },
      })
    } catch {
      showError("Couldn't access microphone — check permissions.")
      return
    }
    streamRef.current = stream

    const mime = bestMimeType()
    const opts = mime ? { mimeType: mime, audioBitsPerSecond: 128_000 } : {}
    const rec  = new MediaRecorder(stream, opts)
    const actualMime = rec.mimeType || mime || 'audio/webm'
    recorderRef.current = rec

    rec.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
    rec.onstop = async () => {
      stream.getTracks().forEach(t => t.stop())
      streamRef.current = null
      if (!shouldSend.current) return
      const blob = new Blob(chunksRef.current, { type: actualMime })
      await sendAudio(blob, actualMime)
    }

    rec.start(250)
    startRef.current = Date.now()
    setTimeout(() => {
      if (recorderRef.current?.state === 'recording') setStage('recording')
    }, ENCODER_WARMUP_MS)
  }, [sendAudio])

  const handleClick = useCallback(async () => {
    if (stage === 'recording') { stopRecording(); return }
    if (['processing', 'speaking'].includes(stage)) return
    setStage('connecting')
    await startRecording()
  }, [stage, startRecording, stopRecording])

  const isBusy  = ['connecting', 'processing', 'speaking'].includes(stage)
  const isError = stage === 'error'
  const isRecording = stage === 'recording'

  const stageLabel = {
    idle:       'Click to talk',
    connecting: 'Connecting…',
    recording:  'Listening… click to stop',
    processing: 'Processing…',
    speaking:   'Speaking…',
    error:      errorMsg || 'Error',
  }[stage] ?? stage

  return (
    <div className="max-w-sm mx-auto flex flex-col items-center gap-4 p-6 border border-gray-200 rounded-2xl shadow-lg bg-white">
      <audio ref={audioRef} className="hidden" />

      {/* Language selector */}
      <div className="flex gap-1.5">
        {LANGUAGES.map(l => (
          <button
            key={l.code}
            onClick={() => handleLangChange(l.code)}
            disabled={isBusy || isRecording}
            className={`px-2.5 py-1 rounded-full text-xs font-medium border transition-colors disabled:opacity-40 ${
              lang === l.code
                ? 'bg-accent border-accent text-white'
                : 'border-gray-200 text-gray-500 hover:border-gray-400'
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>

      {/* Mic button */}
      <button
        onClick={handleClick}
        disabled={isBusy && !isRecording}
        className={`w-20 h-20 rounded-full flex items-center justify-center transition-colors select-none shadow-md ${
          isRecording
            ? 'bg-red-500 hover:bg-red-600 animate-pulse'
            : isError
            ? 'bg-gray-400'
            : 'bg-accent hover:opacity-90'
        } disabled:opacity-60`}
      >
        {stage === 'recording'   ? <MicOff  className="w-8 h-8 text-white" />
        : stage === 'processing' ? <Loader2 className="w-8 h-8 text-white animate-spin" />
        : stage === 'speaking'   ? <Volume2 className="w-8 h-8 text-white" />
        :                          <Mic     className="w-8 h-8 text-white" />}
      </button>

      <p className={`text-sm text-center min-h-[1.25rem] ${isError ? 'text-red-500' : 'text-gray-500'}`}>
        {stageLabel}
      </p>

      {transcript && !isError && (
        <p className="text-xs text-gray-400 text-center italic">"{transcript}"</p>
      )}
      {replyText && !isError && (
        <p className="text-sm text-gray-700 text-center leading-relaxed bg-gray-50 rounded-xl p-3 w-full">
          {replyText}
        </p>
      )}

      {history.length > 0 && (
        <button
          onClick={() => { setHistory([]); setTranscript(''); setReplyText('') }}
          className="text-xs text-gray-400 hover:text-gray-600 underline"
        >
          Clear conversation
        </button>
      )}
    </div>
  )
}
