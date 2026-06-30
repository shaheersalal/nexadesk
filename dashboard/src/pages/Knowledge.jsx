import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Upload, FileText, Trash2, CheckCircle, AlertCircle, Loader, CheckCheck, Mic, MicOff, Square } from 'lucide-react'

const CATEGORIES = ['faq', 'listing', 'policy', 'brochure', 'notes', 'other']
const ACCEPT = '.pdf,.docx,.doc,.txt,.csv,.xlsx,.pptx,.png,.jpg,.jpeg,.html'

function QualityBadge({ score }) {
  const pct = Math.round(score * 100)
  const color = pct >= 70 ? 'text-green-600' : pct >= 40 ? 'text-yellow-600' : 'text-red-500'
  return <span className={`text-xs font-medium ${color}`}>{pct}% quality</span>
}

function StatusIcon({ status }) {
  if (status === 'completed') return <CheckCircle className="w-4 h-4 text-green-500" />
  if (status === 'failed')    return <AlertCircle className="w-4 h-4 text-red-400" />
  return <Loader className="w-4 h-4 text-gray-400 animate-spin" />
}

function Toast({ message, onDone }) {
  useEffect(() => {
    const t = setTimeout(onDone, 4000)
    return () => clearTimeout(t)
  }, [onDone])
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 bg-gray-900 text-white text-sm px-5 py-3 rounded-xl shadow-lg">
      <CheckCheck className="w-4 h-4 text-green-400 flex-shrink-0" />
      {message}
    </div>
  )
}

export default function Knowledge() {
  const [documents, setDocuments] = useState([])
  const [dragging, setDragging] = useState(false)
  const [processingCount, setProcessingCount] = useState(0)
  const [textInput, setTextInput] = useState('')
  const [textTitle, setTextTitle] = useState('')
  const [textCategory, setTextCategory] = useState('notes')
  const [uploadCategory, setUploadCategory] = useState('other')
  const [toast, setToast] = useState(null)
  const fileRef = useRef()

  // Voice recording state
  const [recording, setRecording] = useState(false)
  const [transcribing, setTranscribing] = useState(false)
  const [recordSeconds, setRecordSeconds] = useState(0)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const timerRef = useRef(null)

  function showToast(msg) {
    setToast(msg)
  }

  useEffect(() => {
    api.getDocuments().then(setDocuments).catch(console.error)
  }, [])

  // Poll Supabase documents until processing ones complete
  useEffect(() => {
    if (processingCount === 0) return
    const interval = setInterval(() => {
      api.getDocuments().then((docs) => {
        setDocuments(docs)
        const stillPending = docs.filter((d) => d.status === 'processing').length
        setProcessingCount(stillPending)
      }).catch(console.error)
    }, 3000)
    return () => clearInterval(interval)
  }, [processingCount])

  async function handleFiles(files) {
    let queued = 0
    for (const file of files) {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('category', uploadCategory)
      const res = await api.ingestFile(fd).catch(() => null)
      if (res?.job_id) queued++
    }
    if (queued > 0) {
      setProcessingCount((n) => n + queued)
      showToast(`${queued === 1 ? 'File' : `${queued} files`} uploaded — indexing in background`)
      api.getDocuments().then(setDocuments).catch(console.error)
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    handleFiles([...e.dataTransfer.files])
  }

  async function handleTextSubmit() {
    if (!textInput.trim()) return
    const title = textTitle || 'Pasted text'
    const text = textInput
    const category = textCategory
    setTextInput('')
    setTextTitle('')
    const res = await api.ingestText({ text, category, title }).catch(() => null)
    if (res?.job_id) {
      setProcessingCount((n) => n + 1)
      showToast('Text added — indexing in background')
      api.getDocuments().then(setDocuments).catch(console.error)
    }
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      chunksRef.current = []
      const mr = new MediaRecorder(stream)
      mr.ondataavailable = e => { if (e.data.size > 0) chunksRef.current.push(e.data) }
      mr.onstop = handleRecordingStop
      mediaRecorderRef.current = mr
      mr.start(250) // collect chunks every 250ms
      setRecording(true)
      setRecordSeconds(0)
      timerRef.current = setInterval(() => setRecordSeconds(s => s + 1), 1000)
    } catch {
      showToast('Microphone access denied')
    }
  }

  function stopRecording() {
    clearInterval(timerRef.current)
    mediaRecorderRef.current?.stop()
    mediaRecorderRef.current?.stream.getTracks().forEach(t => t.stop())
    setRecording(false)
  }

  async function handleRecordingStop() {
    setTranscribing(true)
    const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4'
    const blob = new Blob(chunksRef.current, { type: mimeType })
    const ext = mimeType.includes('webm') ? 'webm' : 'mp4'
    const fd = new FormData()
    fd.append('audio', blob, `recording.${ext}`)
    fd.append('category', 'notes')
    try {
      const res = await api.ingestVoice(fd)
      if (res?.job_id) {
        setProcessingCount(n => n + 1)
        showToast('Voice note transcribed and indexed')
        api.getDocuments().then(setDocuments).catch(console.error)
      }
    } catch {
      showToast('Transcription failed — please try again')
    } finally {
      setTranscribing(false)
      setRecordSeconds(0)
    }
  }

  function formatTime(s) {
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
  }

  async function handleDelete(id) {
    if (!confirm('Remove this document from the knowledge base?')) return
    await api.deleteDocument(id)
    setDocuments((prev) => prev.filter((d) => d.id !== id))
  }

  const pendingDocs = documents.filter((d) => d.status === 'processing')

  return (
    <div className="p-4 md:p-8 max-w-4xl">
      {toast && <Toast message={toast} onDone={() => setToast(null)} />}

      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-gray-900">Knowledge Base</h1>
        <p className="text-gray-500 text-sm mt-1">
          Upload any document or paste text — the AI will parse, clean, and index it automatically.
        </p>
      </div>

      {/* Upload zone */}
      <div className="card mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Upload Documents</h2>
        <div className="flex items-center gap-4 mb-4">
          <label className="text-xs text-gray-500">Category</label>
          <select
            value={uploadCategory}
            onChange={(e) => setUploadCategory(e.target.value)}
            className="border border-gray-200 rounded-md px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors ${
            dragging ? 'border-accent bg-accent/5' : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
          }`}
        >
          <Upload className="w-8 h-8 text-gray-300 mx-auto mb-3" />
          <p className="text-sm text-gray-500 font-medium">Drag & drop files here, or click to browse</p>
          <p className="text-xs text-gray-400 mt-1">
            Export your listings as CSV/Excel from your portal account, or just snap a photo of a printed listing sheet — Nexa reads both.
            Also takes PDF, DOCX, PPTX, TXT.
          </p>
          <input ref={fileRef} type="file" accept={ACCEPT} multiple className="hidden" onChange={(e) => handleFiles([...e.target.files])} />
        </div>
      </div>

      {/* Voice recording */}
      <div className="card mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-1">Record a Voice Note</h2>
        <p className="text-xs text-gray-400 mb-4">
          Speak naturally — describe your properties, prices, policies, or anything. Nexa will transcribe, clean, and index it automatically.
        </p>

        <div className="flex items-center gap-5">
          {/* Mic button */}
          {!transcribing && (
            <button
              onClick={recording ? stopRecording : startRecording}
              className={`w-14 h-14 rounded-full flex items-center justify-center transition-all flex-shrink-0 ${
                recording
                  ? 'bg-red-500 hover:bg-red-600 shadow-lg shadow-red-200 animate-pulse'
                  : 'bg-navy-600 hover:bg-navy-700 shadow-md'
              }`}
            >
              {recording
                ? <Square className="w-5 h-5 text-white fill-white" />
                : <Mic className="w-6 h-6 text-white" />
              }
            </button>
          )}

          {/* Status text */}
          <div className="flex-1">
            {transcribing ? (
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <Loader className="w-4 h-4 animate-spin text-accent" />
                Transcribing and indexing your voice note…
              </div>
            ) : recording ? (
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                  <span className="text-sm font-semibold text-gray-800">Recording — {formatTime(recordSeconds)}</span>
                </div>
                <p className="text-xs text-gray-400">Speak clearly. Press the stop button when done.</p>
              </div>
            ) : (
              <div>
                <p className="text-sm text-gray-600 font-medium">Press to start recording</p>
                <p className="text-xs text-gray-400 mt-0.5">Works best in a quiet environment. No time limit.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Text paste */}
      <div className="card mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Paste Text or Notes</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-3">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Title (optional)</label>
            <input
              value={textTitle}
              onChange={(e) => setTextTitle(e.target.value)}
              placeholder="e.g. Company FAQ"
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Category</label>
            <select
              value={textCategory}
              onChange={(e) => setTextCategory(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
            >
              {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>
        <textarea
          value={textInput}
          onChange={(e) => setTextInput(e.target.value)}
          placeholder="Paste any text here — handwritten notes, messy listings, FAQs, company policies… The AI will handle it."
          rows={6}
          className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent resize-none"
        />
        <div className="flex justify-end mt-3">
          <button
            onClick={handleTextSubmit}
            disabled={!textInput.trim()}
            className="btn-primary"
          >
            Ingest Text
          </button>
        </div>
      </div>

      {/* Document list */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-gray-700">Indexed Documents ({documents.length})</h2>
          {pendingDocs.length > 0 && (
            <span className="flex items-center gap-1.5 text-xs text-gray-400">
              <Loader className="w-3.5 h-3.5 animate-spin" />
              {pendingDocs.length} indexing…
            </span>
          )}
        </div>
        {documents.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">No documents indexed yet</p>
        ) : (
          <div className="space-y-2">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center gap-4 py-2.5 border-b border-gray-50 last:border-0">
                <FileText className="w-4 h-4 text-gray-300 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-gray-700 font-medium truncate">{doc.filename}</p>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs text-gray-400 capitalize">{doc.category}</span>
                    {doc.chunk_count > 0 && (
                      <>
                        <span className="text-xs text-gray-300">·</span>
                        <span className="text-xs text-gray-400">{doc.chunk_count} chunks</span>
                      </>
                    )}
                    {doc.quality_score != null && (
                      <>
                        <span className="text-xs text-gray-300">·</span>
                        <QualityBadge score={doc.quality_score} />
                      </>
                    )}
                  </div>
                </div>
                <StatusIcon status={doc.status} />
                <button onClick={() => handleDelete(doc.id)} className="text-gray-300 hover:text-red-400 transition-colors">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
