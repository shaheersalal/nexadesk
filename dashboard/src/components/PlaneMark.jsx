/**
 * The aeroplane mark, shared with the landing page's flight path.
 *
 * Same plan-view silhouette, same swept wings and tailplane — carrying the
 * motif through the sign-in boundary so the product looks like one thing
 * either side of it. Sized and coloured by the caller, and nudged to point
 * up-and-right so it reads as climbing rather than parked.
 */
export default function PlaneMark({ className = '', title }) {
  return (
    <svg
      viewBox="-18 -18 36 36"
      className={className}
      fill="currentColor"
      role={title ? 'img' : 'presentation'}
      aria-hidden={title ? undefined : 'true'}
      aria-label={title}
    >
      <g transform="rotate(-45)">
        <path
          d="M 16 0 L 5 1.9 L 1 2 L -6 11 L -8.5 11 L -4.5 2 L -10 1.8
             L -13.5 5.5 L -15 5.5 L -13.5 1.6 L -16 1.2 L -16 -1.2
             L -13.5 -1.6 L -15 -5.5 L -13.5 -5.5 L -10 -1.8 L -4.5 -2
             L -8.5 -11 L -6 -11 L 1 -2 L 5 -1.9 Z"
        />
      </g>
    </svg>
  )
}
