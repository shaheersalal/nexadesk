import { Link } from 'react-router-dom'

export default function EmptyState({ icon: Icon, title, hint, actionLabel, actionTo, onAction }) {
  return (
    <div className="text-center py-10">
      {Icon && <Icon className="w-8 h-8 text-gray-200 mx-auto mb-3" />}
      <p className="text-sm font-medium text-gray-600">{title}</p>
      {hint && <p className="text-xs text-gray-400 mt-1 max-w-xs mx-auto leading-relaxed">{hint}</p>}
      {actionLabel && actionTo && (
        <Link to={actionTo} className="inline-block text-xs font-semibold text-accent-ink hover:text-accent-ink-h mt-3">
          {actionLabel} →
        </Link>
      )}
      {actionLabel && onAction && !actionTo && (
        <button onClick={onAction} className="text-xs font-semibold text-accent-ink hover:text-accent-ink-h mt-3">
          {actionLabel} →
        </button>
      )}
    </div>
  )
}
