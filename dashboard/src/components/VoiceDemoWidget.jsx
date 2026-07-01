import { useState, useRef, useCallback } from 'react'
import { Mic, Loader2, Volume2 } from 'lucide-react'

const DEFAULT_API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const CONNECT_TIMEOUT_MS = 5000
const FALLBACK_MSG = "Demo is warming up — try again in a moment."

function wsUrl(apiBase) {
  return apiBase.replace(/^http/, 'ws') + '/voice-demo/stream'
}

const STAGE_LABELS = {
  idle: 'Hold to talk',
  connecting: 'Connecting…',
  recording: 'Listening… release to send',
  transcribing: 'Transcribing…',
  thinking: 'Thinking…',
  speaking: 'Speaking…',
}

const BUSY_STAGES = ['connecting', 'transcribing', 'thinking', 'speaking']

/**
 * Self-contained push-to-talk voice demo. Pass `apiBase` to point it at any
 * backend running the WS /voice-demo/stream endpoint — same component drops
 * onto nexadesk.site or shaheer.dev unchanged.
 */
export default function VoiceDemoWidget({ apiBase = DEFAULT_API_BASE }) {
  const [stage, setStage] = useState('idle')
  const [transcript, setTranscript] = useState('')
  const [replyText, setReplyText] = useState('')
  const [errorMsg, setErrorMsg] = useState('')

  const wsRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const audioRef = useRef(null)

  const showFallback = useCallback((msg) => {
    setStage('error')
    setErrorMsg(msg || FALLBACK_MSG)
  }, [])

  const handleMessage = useCallback((event) => {
    if (typeof event.data === 'string') {
      let msg
      try {
        msg = JSON.parse(event.data)
      } catch {
        return
      }
      if (msg.type === 'status') setStage(msg.stage)
      else if (msg.type === 'transcript') setTranscript(msg.text)
      else if (msg.type === 'reply_text') setReplyText(msg.text)
      else if (msg.type === 'error') showFallback(msg.message)
    } else {
      const blob = new Blob([event.data], { type: 'audio/mpeg' })
      const url = URL.createObjectURL(blob)
      if (audioRef.current) {
        audioRef.current.src = url
        audioRef.current.play().catch(() => {})
      }
    }
  }, [showFallback])

  const ensureSocket = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      return Promise.resolve(wsRef.current)
    }
    return new Promise((resolve, reject) => {
      let settled = false
      const ws = new WebSocket(wsUrl(apiBase))
      ws.binaryType = 'arraybuffer'

      const timeout = setTimeout(() => {
        if (settled) return
        settled = true
        ws.close()
        reject(new Error('connect_timeout'))
      }, CONNECT_TIMEOUT_MS)

      ws.onopen = () => {
        if (settled) return
        settled = true
        clearTimeout(timeout)
        wsRef.current = ws
        resolve(ws)
      }
      ws.onerror = () => {
        if (settled) return
        settled = true
        clearTimeout(timeout)
        reject(new Error('connect_error'))
      }
      ws.onmessage = handleMessage
      ws.onclose = () => { wsRef.current = null }
    })
  }, [apiBase, handleMessage])

  const startRecording = useCallback(async () => {
    if (BUSY_STAGES.includes(stage)) return
    setErrorMsg('')
    setTranscript('')
    setReplyText('')
    setStage('connecting')

    let ws
    try {
      ws = await ensureSocket()
    } catch {
      showFallback()
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      chunksRef.current = []
      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop())
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const buf = await blob.arrayBuffer()
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(buf)
        } else {
          showFallback()
        }
      }
      mediaRecorderRef.current = recorder
      recorder.start()
      setStage('recording')
    } catch {
      showFallback("Couldn't access your microphone — check your browser permissions.")
    }
  }, [stage, ensureSocket, showFallback])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop()
      setStage('transcribing')
    }
  }, [])

  const isError = stage === 'error'
  const isRecording = stage === 'recording'
  const isBusy = BUSY_STAGES.includes(stage)
  const label = isError ? errorMsg : STAGE_LABELS[stage]

  return (
    <div className="max-w-sm mx-auto flex flex-col items-center gap-4 p-6 border border-gray-200 rounded-2xl shadow-lg bg-white">
      <audio ref={audioRef} onEnded={() => setStage('idle')} className="hidden" />

      <button
        onMouseDown={startRecording}
        onMouseUp={stopRecording}
        onMouseLeave={() => isRecording && stopRecording()}
        onTouchStart={(e) => { e.preventDefault(); startRecording() }}
        onTouchEnd={(e) => { e.preventDefault(); stopRecording() }}
        disabled={isBusy}
        className={`w-20 h-20 rounded-full flex items-center justify-center transition-colors select-none ${
          isRecording ? 'bg-red-500 animate-pulse' : 'bg-accent hover:bg-accent-dark'
        } text-white disabled:opacity-60`}
        title="Hold to talk"
      >
        {['connecting', 'transcribing', 'thinking'].includes(stage) ? (
          <Loader2 className="w-7 h-7 animate-spin" />
        ) : stage === 'speaking' ? (
          <Volume2 className="w-7 h-7" />
        ) : (
          <Mic className="w-7 h-7" />
        )}
      </button>

      <p className={`text-sm text-center ${isError ? 'text-red-500' : 'text-gray-500'}`}>
        {label}
      </p>

      {transcript && !isError && (
        <p className="text-xs text-gray-400 text-center italic">"{transcript}"</p>
      )}
      {replyText && !isError && (
        <p className="text-sm text-gray-700 text-center leading-relaxed">{replyText}</p>
      )}
    </div>
  )
}
