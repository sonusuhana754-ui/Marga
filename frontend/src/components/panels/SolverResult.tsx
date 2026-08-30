import { Eye } from 'lucide-react'
import type { OptimizeResponse, SolverId } from '@/types/api'
import { fmtKm, fmtPct, fmtSeconds } from '@/lib/format'
import { SOLVERS } from '@/config'

interface SolverResultProps {
  runs: Partial<Record<SolverId, OptimizeResponse>>
  active: SolverId
}

export function SolverResult({ runs, active }: SolverResultProps) {
  const ours = runs.va_qpso
  const base = runs.ortools
  if (!ours || !base) return null

  const costDelta = (ours.total_cost - base.total_cost) / base.total_cost
  const speedRatio = ours.runtime_ms / base.runtime_ms

  return (
    <div className="panel w-[272px] overflow-hidden">
      <div className="border-b border-line px-4 py-2.5">
        <span className="label-mono">Solver comparison</span>
      </div>

      <div className="grid grid-cols-2 divide-x divide-line">
        {SOLVERS.map((s) => {
          const run = runs[s.id]
          if (!run) return null
          return (
            <div key={s.id} className="px-3.5 py-3">
              <div className="flex items-center gap-1.5">
                <span
                  className={`text-[12px] font-semibold ${s.kind === 'ours' ? 'text-marga' : 'text-ink-dim'}`}
                >
                  {s.label}
                </span>
                {active === s.id && <Eye className="h-3 w-3 text-ink-mute" />}
              </div>
              <div className="tnum mt-1.5 text-[18px] font-semibold text-ink">
                {fmtKm(run.total_cost)}
              </div>
              <div className="tnum text-[11px] text-ink-mute">
                {fmtSeconds(run.runtime_ms)} · {run.vehicles_used} vehicles
              </div>
            </div>
          )
        })}
      </div>

      <div className="border-t border-line bg-surface-2/40 px-4 py-3 text-[11.5px] leading-relaxed text-ink-dim">
        On this scenario VA-QPSO is{' '}
        <span className={costDelta < 0 ? 'text-green' : 'text-red'}>
          {fmtPct(Math.abs(costDelta))} {costDelta < 0 ? 'lower' : 'higher'} cost
        </span>{' '}
        and{' '}
        <span className="text-amber">{speedRatio.toFixed(1)}× slower</span>. Standard
        benchmarks tell the other half of the story — see the Benchmark Lab.
      </div>
    </div>
  )
}
