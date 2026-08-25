/**
 * Base URL for the NexaDesk backend.
 *
 * The demo used to call OpenAI directly from Next.js API routes, carrying its
 * own copy of the system prompt. That copy drifted from the backend's, so the
 * demo stopped representing the product. Both widgets now call the real API,
 * which means one prompt, one model config, one set of provider credentials.
 *
 * Set NEXT_PUBLIC_API_URL in the Vercel project settings.
 *
 * The default is the Railway-issued origin, not api.nexadesk.site. The custom
 * domain resolves to Railway but Railway has never issued a certificate for it,
 * so every request from the browser died in the TLS handshake and the widgets
 * looked dead with nothing in the network tab worth reading. Defaulting to the
 * origin that is always valid means the demo works with no env var set at all;
 * point NEXT_PUBLIC_API_URL at the custom domain once its cert is issued.
 */
export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'https://nexadesk-api-production.up.railway.app'

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
