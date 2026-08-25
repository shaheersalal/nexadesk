import { useEffect, useRef, useState } from 'react'

/** True when the visitor has asked the OS for reduced motion. Live-updating. */
export function useReducedMotion() {
  const [reduced, setReduced] = useState(() =>
    typeof window !== 'undefined' &&
    window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  )
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    const on = e => setReduced(e.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return reduced
}

/**
 * Scroll progress of `ref` through the viewport, 0 to 1.
 *
 * Driven by rAF off a passive scroll listener rather than a CSS scroll
 * timeline: scroll-driven animations are still missing from Firefox and older
 * Safari, and the horizontal section is not decorative — without movement a
 * visitor sees one card and no sign the rest exist. Reveals do use the CSS
 * timeline (see flight.css) because those degrade safely to "visible".
 *
 * Returns 0 under reduced motion so callers render a static state.
 */
export function useScrollProgress(ref, { disabled = false } = {}) {
  const [progress, setProgress] = useState(0)
  const frame = useRef(0)

  useEffect(() => {
    if (disabled) { setProgress(0); return }
    const el = ref.current
    if (!el) return

    const measure = () => {
      frame.current = 0
      const r = el.getBoundingClientRect()
      const travel = r.height - window.innerHeight
      if (travel <= 0) { setProgress(0); return }
      setProgress(Math.min(1, Math.max(0, -r.top / travel)))
    }
    const onScroll = () => {
      if (frame.current) return
      frame.current = requestAnimationFrame(measure)
    }

    measure()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (frame.current) cancelAnimationFrame(frame.current)
    }
  }, [ref, disabled])

  return progress
}

/** Whole-document scroll progress, 0 to 1. Draws the flight path. */
export function useDocumentProgress({ disabled = false } = {}) {
  const [progress, setProgress] = useState(0)
  const frame = useRef(0)

  useEffect(() => {
    if (disabled) { setProgress(1); return }   // reduced motion: fully drawn
    const measure = () => {
      frame.current = 0
      const doc = document.documentElement
      const travel = doc.scrollHeight - window.innerHeight
      setProgress(travel <= 0 ? 0 : Math.min(1, Math.max(0, window.scrollY / travel)))
    }
    const onScroll = () => {
      if (frame.current) return
      frame.current = requestAnimationFrame(measure)
    }
    measure()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll, { passive: true })
    return () => {
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      if (frame.current) cancelAnimationFrame(frame.current)
    }
  }, [disabled])

  return progress
}
