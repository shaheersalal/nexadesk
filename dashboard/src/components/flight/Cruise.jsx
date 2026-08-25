import { useRef } from 'react'
import { useScrollProgress, useReducedMotion } from './useFlight'

/**
 * The cruise segment — the one place the page travels sideways.
 *
 * A tall track pins a full-height stage while the rail inside it translates on
 * X, so vertical scrolling reads as forward motion: the aircraft advances, the
 * world moves right-to-left past the window.
 *
 * Two rules keep this from being scroll-jacking. The page never takes over the
 * wheel — scroll distance maps 1:1 to track height, so the visitor can stop,
 * reverse and leave at any moment. And under reduced motion the stage un-pins
 * into an ordinary horizontally scrollable list (flight.css), which is a real
 * fallback rather than a frozen section.
 */
export default function Cruise({ eyebrow, heading, intro, items }) {
  const track = useRef(null)
  const reduced = useReducedMotion()
  const p = useScrollProgress(track, { disabled: reduced })

  // Leave the first card on screen briefly before travel begins.
  const eased = Math.max(0, (p - 0.06) / 0.88)
  const shift = Math.min(1, eased)

  return (
    <section
      ref={track}
      className="cruise-track"
      style={{ height: reduced ? 'auto' : `${Math.max(260, items.length * 78)}vh` }}
      aria-label={heading}
    >
      <div className="cruise-stage">
        <div className="w-full">
          <div className="mx-auto mb-10 max-w-[var(--measure)] px-[max(6vw,28px)]">
            {eyebrow && (
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.18em]"
                 style={{ color: 'var(--accent)' }}>
                {eyebrow}
              </p>
            )}
            <h2 className="text-3xl md:text-[2.6rem] font-semibold tracking-[-0.025em] leading-[1.08]">
              {heading}
            </h2>
            {intro && (
              <p className="mt-3 max-w-xl text-[15px] leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
                {intro}
              </p>
            )}
          </div>

          <div
            className="cruise-rail"
            style={
              reduced
                ? undefined
                : { transform: `translate3d(calc(${-shift} * (100% - 100vw + 12vw)), 0, 0)` }
            }
          >
            {items.map((it, i) => (
              <article
                key={it.title}
                className="panel r-lg shrink-0 w-[min(78vw,380px)] p-7"
                style={{ marginTop: i % 2 ? '2.5rem' : 0 }}
              >
                <div className="mb-5 flex items-baseline gap-3">
                  <span className="font-mono text-xs tabular-nums" style={{ color: 'var(--accent)' }}>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="h-px flex-1" style={{ background: 'var(--hairline)' }} />
                </div>
                <h3 className="text-lg font-semibold tracking-[-0.015em]">{it.title}</h3>
                <p className="mt-2.5 text-[14.5px] leading-relaxed" style={{ color: 'var(--ink-soft)' }}>
                  {it.body}
                </p>
                {it.detail && (
                  <p className="mt-4 border-t pt-4 text-[13px] leading-relaxed"
                     style={{ borderColor: 'var(--hairline)', color: 'var(--ink-mute)' }}>
                    {it.detail}
                  </p>
                )}
              </article>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}
