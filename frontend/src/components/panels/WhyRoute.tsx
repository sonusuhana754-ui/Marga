import type { FleetRoute } from '@/types/api'
import { fmtInt, fmtPct } from '@/lib/format'
import { C } from '@/lib/palette'

const TERMS: { key: keyof FleetRoute['decision_weights']; label: string; color: string }[] = [
  { key: 'traffic', label: 'Traffic cost', color: C.red },
  { key: 'distance', label: 'Distance', color: C.marga },
  { key: 'congestion', label: 'Congestion', color: C.amber },
  { key: 'constraints', label: 'Vehicle constraints', color: C.inkMute },
]

/** Why the solver picked this route: the cost terms it weighed, and by how much. */
export function WhyRoute({ route }: { route: FleetRoute }) {
  const w = route.decision_weights
  const total = TERMS.reduce((s, t) => s + w[t.key], 0) || 1
  const [chosen, nextBest] = route.cost_vs_next_best

  return (
    <div className="panel w-full overflow-hidden">
      <div className="border-b border-line px-4 py-2.5">
        <span className="label-mono">Why this route</span>
      </div>

      <div className="px-4 py-3">
        <div className="flex h-3 overflow-hidden rounded-[3px] border border-line">
          {TERMS.map((t) => (
            <span
              key={t.key}
              style={{ width: `${(w[t.key] / total) * 100}%`, background: t.color }}
            />
          ))}
        </div>
        <div className="mt-2.5 flex flex-wrap gap-x-3 gap-y-1">
          {TERMS.map((t) => (
            <span key={t.key} className="flex items-center gap-1.5 text-[10.5px] text-ink-mute">
              <span className="h-2 w-2 rounded-[2px]" style={{ background: t.color }} />
              {t.label}&nbsp;<span className="tnum text-ink-dim">{fmtPct(w[t.key], 0)}</span>
            </span>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 divide-x divide-line border-t border-line text-[11px]">
        <div className="px-4 py-2.5">
          <div className="text-ink-mute">Chosen route cost</div>
          <div className="tnum mt-0.5 text-[14px] font-semibold text-marga">{fmtInt(chosen)}</div>
        </div>
        <div className="px-4 py-2.5">
          <div className="text-ink-mute">Next-best considered</div>
          <div className="tnum mt-0.5 text-[14px] font-semibold text-ink-dim">{fmtInt(nextBest)}</div>
        </div>
      </div>

      <p className="border-t border-line bg-surface-2/40 px-4 py-2.5 text-[10.5px] leading-relaxed text-ink-mute">
        Weights and costs are reported by the solver per route — the frontend
        renders them, it doesn’t compute the weighting.
      </p>
    </div>
  )
}
