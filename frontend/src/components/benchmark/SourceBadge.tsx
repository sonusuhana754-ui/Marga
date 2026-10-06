/**
 * Says in words whether the numbers on screen were measured.
 *
 * The api layer has no fixture path, so `backend` is the only value the
 * benchmark response can carry; the component still renders the alternative
 * because a badge that can only ever say one thing is not a badge.
 */
export function SourceBadge({ source }: { source?: 'backend' }) {
  if (source === 'backend') {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-green/30 bg-green/10 px-2.5 py-1 text-[10px] uppercase tracking-wide text-green">
        <span className="h-1.5 w-1.5 rounded-full bg-green" />
        Measured · live backend
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-amber/30 bg-amber/10 px-2.5 py-1 text-[10px] uppercase tracking-wide text-amber">
      <span className="h-1.5 w-1.5 rounded-full bg-amber" />
      Source unknown · not measured
    </span>
  )
}
