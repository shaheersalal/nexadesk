/**
 * WebWorker: runs Whisper tiny.en in the browser via ONNX Runtime.
 * Model (~40 MB) is downloaded once and cached in IndexedDB by the library.
 *
 * Messages IN  (main → worker):
 *   { type: 'load' }
 *   { type: 'transcribe', audio: Float32Array }  — 16 kHz mono PCM
 *
 * Messages OUT (worker → main):
 *   { type: 'loading' }
 *   { type: 'ready' }
 *   { type: 'transcript', text: string }
 *   { type: 'error', message: string }
 */
import { pipeline, env } from '@huggingface/transformers'

// Use remote HuggingFace models and cache them in browser IndexedDB.
env.allowLocalModels = false
env.useBrowserCache = true

let transcriber = null

async function load() {
  self.postMessage({ type: 'loading' })
  transcriber = await pipeline(
    'automatic-speech-recognition',
    'onnx-community/whisper-tiny.en',
    { dtype: 'q8', device: 'wasm' },
  )
  self.postMessage({ type: 'ready' })
}

self.onmessage = async (e) => {
  const { type, audio } = e.data

  if (type === 'load') {
    try {
      await load()
    } catch (err) {
      self.postMessage({ type: 'error', message: err.message })
    }
    return
  }

  if (type === 'transcribe') {
    if (!transcriber) {
      self.postMessage({ type: 'error', message: 'Model not loaded yet' })
      return
    }
    try {
      const result = await transcriber(audio, { return_timestamps: false })
      self.postMessage({ type: 'transcript', text: result.text.trim() })
    } catch (err) {
      self.postMessage({ type: 'error', message: err.message })
    }
  }
}
