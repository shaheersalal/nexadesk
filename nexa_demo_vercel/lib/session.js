/**
 * One session id per browser tab session (sessionStorage) — ties a page
 * visit and an analytics session together into one id for this demo site.
 */
export function getSessionId() {
  if (typeof window === 'undefined') return ''
  const KEY = 'nexadesk_site_session_id'
  let id = sessionStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID()
    sessionStorage.setItem(KEY, id)
  }
  return id
}
