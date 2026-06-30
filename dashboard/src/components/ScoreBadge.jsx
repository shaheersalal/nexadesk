// Single source of truth for lead-score color tiers — used everywhere a score
// renders (Leads kanban, Lead detail, Dashboard hot-leads panel) so the same
// number always reads the same color across the app.
export function scoreTier(score) {
  if (score >= 70) return { dot: 'bg-green-500', text: 'text-green-700', bg: 'bg-green-50', ring: 'bg-green-500' }
  if (score >= 40) return { dot: 'bg-amber-500', text: 'text-amber-700', bg: 'bg-amber-50', ring: 'bg-amber-400' }
  return { dot: 'bg-red-500', text: 'text-red-600', bg: 'bg-red-50', ring: 'bg-red-400' }
}

export default function ScoreBadge({ score, size = 'sm' }) {
  const value = score ?? 0
  const tier = scoreTier(value)
  const sizeClasses = size === 'sm' ? 'text-xs px-2 py-0.5 gap-1' : 'text-sm px-2.5 py-1 gap-1.5'
  return (
    <span className={`inline-flex items-center rounded-full font-semibold ${tier.bg} ${tier.text} ${sizeClasses}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${tier.dot}`} />
      {value}
    </span>
  )
}
