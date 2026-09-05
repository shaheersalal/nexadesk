'use client'
import { useState, useRef, useCallback } from 'react'
import { postForm } from '@/lib/api'

// English-only for now. Aura has no Arabic or Urdu voice, so offering them
// meant the reply came back as text with silence where the speech should be —
// worse than not offering them. Add the entries back alongside an ElevenLabs
// key; the selector below re-appears on its own once this list has >1 entry.
const LANGUAGES = [
  { code: 'en',   label: 'English'  },
]

const MIN_RECORD_MS    = 1500
const ENCODER_WARMUP_MS = 250

function bestMimeType() {
  const candidates = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg;codecs=opus']
  return candidates.find(t => MediaRecorder.isTypeSupported(t)) ?? ''
}

export default function VoiceWidget() {
  const [stage, setStage]           = useState('idle')   // idle | recording | processing | speaking | error
  const [lang, setLang]             = useState('en')
  const [transcript, setTranscript] = useState('')
  const [replyText, setReplyText]   = useState('')
  const [errorMsg, setErrorMsg]     = useState('')
  const [history, setHistory]       = useState([])      // [{role, content}]

  const recorderRef  = useRef(null)
  const chunksRef    = useRef([])
  const streamRef    = useRef(null)
  const langRef      = useRef('en')
  const startRef     = useRef(0)
  const shouldSend   = useRef(true)
  const audioRef     = useRef(null)

  const handleLang = (code) => { setLang(code); langRef.current = code }

  const showError = (msg) => { setStage('error'); setErrorMsg(msg) }

  const playBase64Audio = (b64, mime) => {
    setStage('speaking')
    // The server picks the container: parallel clause synthesis returns WAV,
    // the single-shot path returns MP3. Assuming one breaks the other.
    const src = `data:${mime || 'audio/mpeg'};base64,${b64}`
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
      fd.append('lang',  langRef.current)
      fd.append('history', JSON.stringify(history))

      // Real backend: Deepgram STT -> gpt-4o-mini -> Deepgram Aura TTS, the same
      // chain the production phone line uses, rather than a separate OpenAI
      // call path. The reply comes back as base64 MP3 regardless of provider.
      const data = await postForm('/demo/voice', fd)

      setTranscript(data.transcript)
      setReplyText(data.reply)
      setHistory(h => [
        ...h,
        { role: 'user',      content: data.historyUser      },
        { role: 'assistant', content: data.historyAssistant },
      ])
      if (data.audio) {
        playBase64Audio(data.audio, data.audioMime)
      } else {
        // TTS unavailable — the reply text is still shown, so don't fail hard.
        setStage('idle')
      }
    } catch (err) {
      showError(err.message || 'Network error — try again.')
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
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl:  false,
          sampleRate: 48000,
          channelCount: 1,
        },
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

  const stageLabel = {
    idle:       'Click to talk',
    connecting: 'Connecting…',
    recording:  'Listening… click to stop',
    processing: 'Processing…',
    speaking:   'Speaking…',
    error:      errorMsg || 'Error',
  }[stage] ?? stage

  return (
    <div className="flex flex-col items-center gap-4 w-full">
      {/* Language selector — hidden while only one language is offered */}
      <div className={`gap-1.5 flex-wrap justify-center ${LANGUAGES.length > 1 ? 'flex' : 'hidden'}`}>
        {LANGUAGES.map(l => (
          <button
            key={l.code}
            onClick={() => handleLang(l.code)}
            disabled={isBusy || stage === 'recording'}
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

      {/* Mic button */}
      <button
        onClick={handleClick}
        disabled={isBusy && stage !== 'recording'}
        data-track="demo_voice_mic"
        className={`w-20 h-20 rounded-full flex items-center justify-center text-white text-3xl transition-all select-none shadow-lg ${
          stage === 'recording'
            ? 'bg-red-500 hover:bg-red-600 animate-pulse'
            : isError
            ? 'bg-gray-400'
            : 'bg-accent hover:bg-accent-light'
        } disabled:opacity-60`}
        title={stage === 'recording' ? 'Click to stop' : 'Click to talk'}
      >
        {stage === 'recording'   ? '⏹'
        : stage === 'processing' ? '⏳'
        : stage === 'speaking'   ? '🔊'
        : '🎙️'}
      </button>

      <p className={`text-sm text-center min-h-[1.25rem] ${isError ? 'text-red-500' : 'text-gray-500'}`}>
        {stageLabel}
      </p>

      {transcript && !isError && (
        <p className="text-xs text-gray-400 text-center italic">"{transcript}"</p>
      )}
      {replyText && !isError && (
        <p className="text-sm text-gray-700 text-center leading-relaxed bg-gray-50 rounded-lg p-3 w-full">
          {replyText}
        </p>
      )}

      {history.length > 0 && (
        <button
          onClick={() => { setHistory([]); setTranscript(''); setReplyText('') }}
          className="text-xs text-gray-400 hover:text-gray-600 underline mt-1"
        >
          Clear conversation
        </button>
      )}
    </div>
  )
}
