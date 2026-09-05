'use client'

import { useEffect } from 'react'
import { track, trackScrollDepth, initAnalytics } from '@/lib/analytics'

// Single-page demo site — no client-side routing, so path is always '/'.
export default function AnalyticsBeacon() {
  useEffect(() => initAnalytics(), [])

  useEffect(() => {
    track('pageview', '/')
    return trackScrollDepth('/')
  }, [])

  // Any element with data-track="label" fires a click event — used on the
  // CTAs that matter (start chat, start voice call) rather than
  // instrumenting every link.
  useEffect(() => {
    function onClick(e) {
      const el = e.target.closest('[data-track]')
      if (el) track('click', '/', { label: el.dataset.track })
    }
    document.addEventListener('click', onClick)
    return () => document.removeEventListener('click', onClick)
  }, [])

  return null
}
