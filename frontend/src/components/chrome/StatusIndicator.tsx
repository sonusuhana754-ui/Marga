import { Activity, AlertTriangle, Loader2 } from 'lucide-react'
import { useDemo } from '@/state/demoStore'
import { fmtInt } from '@/lib/format'

/**
 * What the backend is actually doing, from local run state. The previous
 * version charted a fixture's `optimization_status` ticks — threshold-crossed
 * and re-optimizing events that never happened. There is no live re-optimization
 * feed, so those states are gone rather than simulated.
 */
export function StatusIndicator() {
  const { status, error, activeRun, solver } = useDemo()

  if (status === 'optimizing') {
    return (
      <div className="panel flex items-center gap-2 border-line px-3 py-2 text-[12px] font-medium text-ink-dim">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Solving · {solver}
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="panel flex max-w-[520px] items-start gap-2 border-red/60 px-3 py-2 text-[12px] font-medium text-red">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span className="break-words">{error}</span>
      </div>
    )
  }

  if (status === 'ready' && activeRun) {
    return (
      <div className="panel flex items-center gap-2 border-line px-3 py-2 text-[12px] font-medium text-ink-dim">
        <Activity className="h-3.5 w-3.5 text-marga" />
        Solved · {activeRun.vehicles_used} vehicles · {fmtInt(activeRun.runtime_ms)} ms ·{' '}
        {activeRun.solver}
      </div>
    )
  }

  return null
}
