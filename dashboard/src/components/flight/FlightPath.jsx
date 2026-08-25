import { useDocumentProgress, useReducedMotion } from './useFlight'

/**
 * The signature detail: one continuous flight path threading the whole page.
 *
 * It taxis flat, rotates at the hero, climbs through the proof and cruise
 * sections, levels off, and settles on approach at the footer — drawn in step
 * with scroll so the page has a single spatial through-line rather than a set
 * of unrelated animated sections. Exactly one signature detail, per the recipe.
 *
 * Deliberately not an aeroplane illustration. A drawn plane at this scale reads
 * as clip-art on a B2B page; the *path* carries the same idea and stays
 * abstract. The marker is a small craft-shaped wedge, not a picture of one.
 */
export default function FlightPath() {
  const reduced = useReducedMotion()
  const p = useDocumentProgress({ disabled: reduced })

  // Runway, rotation, climb, cruise, descent — in a 0-1000 x 0-1000 field.
  const D =
    'M -20 880 L 210 880 C 330 880 360 840 430 720 C 500 600 540 470 640 380 ' +
    'C 740 290 860 250 1020 240'

  const LEN = 1750                       // approximate path length for dashing
  const drawn = Math.max(0.02, p)

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
    >
      <svg
        viewBox="0 0 1000 1000"
        preserveAspectRatio="xMidYMid slice"
        className="h-full w-full"
      >
        <defs>
          <linearGradient id="fp-stroke" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0%"   stopColor="var(--accent-soft)" stopOpacity="0.05" />
            <stop offset="55%"  stopColor="var(--accent)"      stopOpacity="0.45" />
            <stop offset="100%" stopColor="var(--accent)"      stopOpacity="0.85" />
          </linearGradient>
          <filter id="fp-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="7" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Ghost of the whole route — the journey ahead, barely there. */}
        <path
          d={D}
          fill="none"
          stroke="var(--ink)"
          strokeOpacity="0.06"
          strokeWidth="1.5"
          strokeDasharray="7 11"
        />

        {/* The path actually travelled. */}
        <path
          d={D}
          fill="none"
          stroke="url(#fp-stroke)"
          strokeWidth="2.25"
          strokeLinecap="round"
          filter="url(#fp-glow)"
          style={{
            strokeDasharray: LEN,
            strokeDashoffset: LEN * (1 - drawn),
            transition: reduced ? 'none' : 'stroke-dashoffset 90ms linear',
          }}
        />

        {/* Position marker riding the path. */}
        {!reduced && (
          <g style={{ offsetPath: `path("${D}")`, offsetDistance: `${drawn * 100}%`, offsetRotate: 'auto' }}>
            <path d="M -9 0 L 7 -5 L 3 0 L 7 5 Z" fill="var(--accent)" opacity="0.9" />
          </g>
        )}
      </svg>
    </div>
  )
}
