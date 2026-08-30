import { Activity, AlertTriangle, RefreshCw } from 'lucide-react'
import { useDemo } from '@/state/demoStore'
import { useStreamTick } from '@/state/useStreamTick'
import type { OptStatusState } from '@/types/api'

const CONFIG: Record<
  OptStatusState,
  { icon: typeof Activity; text: (z?: string) => string; cls: string; spin?: boolean; pulse?: boolean }
> = {
  stable: {
    icon: Activity,
    text: () => 'Stable · monitoring',
    cls: 'text-ink-dim border-line',
  },
  threshold_crossed: {
    icon: AlertTriangle,
    text: (z) => `Volatility threshold crossed${z ? ` · ${z}` : ''}`,
    cls: 'text-amber border-amber/70',
    pulse: true,
  },
  reoptimizing: {
    icon: RefreshCw,
    text: (z) => `Re-optimizing affected zone${z ? ` ${z}` : ''}`,
    cls: 'text-marga border-marga/70',
    spin: true,
  },
}

export function StatusIndicator() {
  const { stream } = useDemo()
  const tick = useStreamTick(stream)
  if (!tick) return null

  const { state, zone_id } = tick.optimization_status
  const c = CONFIG[state]
  const Icon = c.icon

  return (
    <div
      className={`panel flex items-center gap-2 px-3 py-2 text-[12px] font-medium ${c.cls} ${
        c.pulse ? 'animate-pulse' : ''
      }`}
    >
      <Icon className={`h-3.5 w-3.5 ${c.spin ? 'animate-spin' : ''}`} />
      {c.text(zone_id)}
    </div>
  )
}
