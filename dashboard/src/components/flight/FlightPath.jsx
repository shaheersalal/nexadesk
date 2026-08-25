import { useDocumentProgress, useReducedMotion } from './useFlight'

/**
 * The signature detail: one continuous flight path threading the whole page.
 *
 * It taxis flat, rotates at the hero, climbs through the proof and cruise
 * sections, levels off, and settles on approach at the footer — drawn in step
 * with scroll so the page has a single spatial through-line rather than a set
 * of unrelated animated sections. Exactly one signature detail, per the recipe.
 *
 * The aircraft is a plan-view silhouette in one flat fill — the same language
 * as the aircraft on an airline route map, which is the one context this shape
 * appears in without reading as clip-art. It banks into the climb automatically
 * because offsetRotate follows the path tangent.
 */
export default function FlightPath() {
  const reduced = useReducedMotion()
  const p = useDocumentProgress({ disabled: reduced })

  // Runway, rotation, climb, cruise, descent — in a 0-1000 x 0-1000 field.
  // Kept inside the viewBox rather than running to its edges. The field is
  // letterboxed with `meet`, not cropped with `slice`: slice threw away the top
  // and bottom of the box on a wide viewport, which is exactly where the runway
  // and the top of the climb live — the aircraft spent most of the page
  // off-screen, which defeats the entire idea.
  const D =
    'M 40 820 L 250 820 C 360 820 395 785 460 685 C 530 578 570 452 665 372 ' +
    'C 755 296 880 258 1160 236'

  const LEN = 1620                       // approximate path length for dashing
  const drawn = Math.max(0.02, p)

  return (
    <>
      {/* Trail: behind the page content. */}
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
        <svg
        viewBox="0 0 1200 1000"
        preserveAspectRatio="xMidYMid meet"
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

        </svg>
      </div>

      {/* The aircraft rides in its own layer ABOVE the content.
       *
       * The trail belongs behind the page — it is texture. The aircraft does
       * not: kept at the same depth it spent whole sections hidden behind the
       * cards, which is the one thing this motif cannot afford to do. It stays
       * small, sits below the nav, and never takes pointer events. */}
      {!reduced && (
        <svg
          aria-hidden="true"
          viewBox="0 0 1200 1000"
          preserveAspectRatio="xMidYMid meet"
          className="pointer-events-none fixed inset-0 z-[15] h-full w-full"
        >
          <g style={{ offsetPath: `path("${D}")`, offsetDistance: `${drawn * 100}%`, offsetRotate: 'auto' }}>
            <g transform="scale(1.45)">
              <path
                d="M 16 0 L 5 1.9 L 1 2 L -6 11 L -8.5 11 L -4.5 2 L -10 1.8
                   L -13.5 5.5 L -15 5.5 L -13.5 1.6 L -16 1.2 L -16 -1.2
                   L -13.5 -1.6 L -15 -5.5 L -13.5 -5.5 L -10 -1.8 L -4.5 -2
                   L -8.5 -11 L -6 -11 L 1 -2 L 5 -1.9 Z"
                fill="var(--accent-cta)"
                stroke="var(--sky-high)"
                strokeWidth="1.1"
                strokeLinejoin="round"
              />
            </g>
          </g>
        </svg>
      )}
    </>
  )
}
