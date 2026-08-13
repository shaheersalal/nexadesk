/**
 * Base URL for the NexaDesk backend.
 *
 * The demo used to call OpenAI directly from Next.js API routes, carrying its
 * own copy of the system prompt. That copy drifted from the backend's, so the
 * demo stopped representing the product. Both widgets now call the real API,
 * which means one prompt, one model config, one set of provider credentials.
 *
 * Set NEXT_PUBLIC_API_URL in the Vercel project settings.
 */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'https://api.nexadesk.site'

export async function postJSON(path, body) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return data
}

export async function postForm(path, formData) {
  const res = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    body: formData,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return data
}
