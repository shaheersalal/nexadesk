import { useEffect, useRef, useState } from 'react'
import { api } from '../lib/api'
import { Upload, FileText, Trash2, CheckCircle, AlertCircle, Loader, X } from 'lucide-react'

const CATEGORIES = ['faq', 'listing', 'policy', 'brochure', 'notes', 'other']
const ACCEPT = '.pdf,.docx,.doc,.txt,.csv,.xlsx,.png,.jpg,.jpeg,.html'

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

export default function Knowledge() {
  const [documents, setDocuments] = useState([])
  const [dragging, setDragging] = useState(false)
  const [jobs, setJobs] = useState([]) // {jobId, filename, status}
  const [textInput, setTextInput] = useState('')
  const [textTitle, setTextTitle] = useState('')
  const [textCategory, setTextCategory] = useState('notes')
  const [uploadCategory, setUploadCategory] = useState('other')
  const [submitting, setSubmitting] = useState(false)
  const fileRef = useRef()

  useEffect(() => {
    api.getDocuments().then(setDocuments).catch(console.error)
  }, [])

  // Poll pending jobs
  useEffect(() => {
    const pending = jobs.filter((j) => j.status === 'processing')
    if (!pending.length) return
    const interval = setInterval(async () => {
      const updated = await Promise.all(
        pending.map((j) => api.getJobStatus(j.jobId).catch(() => j))
      )
      setJobs((prev) =>
        prev.map((j) => {
          const u = updated.find((x) => x.job_id === j.jobId)
          if (u && u.status !== 'processing') {
            if (u.status === 'completed') {
              api.getDocuments().then(setDocuments).catch(console.error)
            }
            return { ...j, status: u.status, error: u.error }
          }
          return j
        })
      )
    }, 2000)
    return () => clearInterval(interval)
  }, [jobs])

  async function handleFiles(files) {
    for (const file of files) {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('category', uploadCategory)
      const res = await api.ingestFile(fd).catch((e) => ({ error: e.message }))
      if (res.job_id) {
        setJobs((prev) => [...prev, { jobId: res.job_id, filename: file.name, status: 'processing' }])
      }
    }
  }

  function onDrop(e) {
    e.preventDefault()
    setDragging(false)
    handleFiles([...e.dataTransfer.files])
  }

  async function handleTextSubmit() {
    if (!textInput.trim()) return
    setSubmitting(true)
    await api.ingestText({ text: textInput, category: textCategory, title: textTitle || 'Pasted text' })
    setTextInput('')
    setTextTitle('')
    api.getDocuments().then(setDocuments).catch(console.error)
    setSubmitting(false)
  }

  async function handleDelete(id) {
    if (!confirm('Remove this document from the knowledge base?')) return
    await api.deleteDocument(id)
    setDocuments((prev) => prev.filter((d) => d.id !== id))
  }

  return (
    <div className="p-4 md:p-8 max-w-4xl">
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
          <p className="text-xs text-gray-400 mt-1">PDF, DOCX, XLSX, TXT, CSV, PNG, JPG — messy docs welcome</p>
          <input ref={fileRef} type="file" accept={ACCEPT} multiple className="hidden" onChange={(e) => handleFiles([...e.target.files])} />
        </div>

        {/* Active jobs */}
        {jobs.length > 0 && (
          <div className="mt-4 space-y-2">
            {jobs.map((job, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <StatusIcon status={job.status} />
                <span className="text-gray-600 flex-1 truncate">{job.filename}</span>
                <span className="text-xs text-gray-400 capitalize">{job.status}</span>
                {job.error && <span className="text-xs text-red-400">{job.error}</span>}
              </div>
            ))}
          </div>
        )}
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
            disabled={submitting || !textInput.trim()}
            className="btn-primary"
          >
            {submitting ? 'Processing…' : 'Ingest Text'}
          </button>
        </div>
      </div>

      {/* Document list */}
      <div className="card">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Indexed Documents ({documents.length})</h2>
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
                    <span className="text-xs text-gray-300">·</span>
                    <span className="text-xs text-gray-400">{doc.chunk_count} chunks</span>
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
