/**
 * First-party analytics beacon for app/analytics/router.py::POST /track in
 * nexa_desk — owner-only (Shaheer sees this in the dashboard's Site
 * Analytics page, gated to his own login). Batches events and flushes on an
 * interval and on page hide, using sendBeacon so the send survives the tab
 * actually closing. Ported from shaheer-dev-next/lib/analytics.js — same
 * backend endpoint, `site: "nexadesk_site"` instead of `"shaheer_dev"`.
 */
import { API_URL } from './api'
import { getSessionId } from './session'

const SITE = 'nexadesk_site'
const FLUSH_INTERVAL_MS = 8000

let queue = []
let flushTimer = null

function flush() {
  if (queue.length === 0) return
  const events = queue.splice(0, queue.length)
  const payload = JSON.stringify({
    site: SITE,
    session_id: getSessionId(),
    referrer: typeof document !== 'undefined' ? document.referrer.slice(0, 500) : '',
    events,
  })

  const url = `${API_URL}/analytics/track`
  try {
    if (navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' })
      const ok = navigator.sendBeacon(url, blob)
      if (ok) return
    }
  } catch (_) { /* fall through to fetch */ }

  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload,
    keepalive: true,
  }).catch(() => {})
}

function scheduleFlush() {
  if (flushTimer) return
  flushTimer = setTimeout(() => {
    flushTimer = null
    flush()
  }, FLUSH_INTERVAL_MS)
}

export function track(eventType, path, eventData = {}) {
  if (typeof window === 'undefined') return
  queue.push({ event_type: eventType, path, event_data: eventData })
  scheduleFlush()
}

export function initAnalytics() {
  if (typeof window === 'undefined') return () => {}

  const onHide = () => {
    if (document.visibilityState === 'hidden') flush()
  }
  document.addEventListener('visibilitychange', onHide)
  window.addEventListener('pagehide', flush)

  return () => {
    document.removeEventListener('visibilitychange', onHide)
    window.removeEventListener('pagehide', flush)
  }
}

// ── Scroll-depth tracking ──────────────────────────────────────────────────

const SCROLL_MILESTONES = [25, 50, 75, 100]

export function trackScrollDepth(path) {
  if (typeof window === 'undefined') return () => {}
  const fired = new Set()

  function onScroll() {
    const doc = document.documentElement
    const scrolled = doc.scrollTop + window.innerHeight
    const total = doc.scrollHeight
    if (total <= 0) return
    const pct = Math.min(100, Math.round((scrolled / total) * 100))
    for (const milestone of SCROLL_MILESTONES) {
      if (pct >= milestone && !fired.has(milestone)) {
        fired.add(milestone)
        track('scroll_depth', path, { depth_pct: milestone })
      }
    }
  }

  window.addEventListener('scroll', onScroll, { passive: true })
  return () => window.removeEventListener('scroll', onScroll)
}
