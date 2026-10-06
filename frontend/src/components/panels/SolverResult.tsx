import { Eye } from 'lucide-react'
import type { OptimizeResponse, SolverId } from '@/types/api'
import { fmtKm, fmtPct, fmtSeconds } from '@/lib/format'
import { SOLVERS } from '@/config'

interface SolverResultProps {
  runs: Partial<Record<SolverId, OptimizeResponse>>
  active: SolverId
}

export function SolverResult({ runs, active }: SolverResultProps) {
  const present = SOLVERS.map((s) => ({ ...s, run: runs[s.id] })).filter((s) => s.run)
  if (present.length === 0) return null

  const ours = runs.va_qpso
  const base = runs.ortools
  // A cost *comparison* needs two solvers. With one, the footer says what that
  // solver actually measured rather than inventing a delta.
  const comparable = Boolean(ours && base && base.total_cost > 0)

  return (
    <div className="panel w-[272px] overflow-hidden">
      <div className="border-b border-line px-4 py-2.5">
        <span className="label-mono">Solver comparison</span>
      </div>

      <div
        className="grid divide-x divide-line"
        style={{ gridTemplateColumns: `repeat(${present.length}, minmax(0, 1fr))` }}
      >
        {present.map(({ id, label, kind, run }) => (
          <div key={id} className="px-3.5 py-3">
            <div className="flex items-center gap-1.5">
              <span
                className={`text-[12px] font-semibold ${kind === 'ours' ? 'text-marga' : 'text-ink-dim'}`}
              >
                {label}
              </span>
              {active === id && <Eye className="h-3 w-3 text-ink-mute" />}
            </div>
            <div className="tnum mt-1.5 text-[18px] font-semibold text-ink">
              {fmtKm(run!.total_cost)}
            </div>
            <div className="tnum text-[11px] text-ink-mute">
              {fmtSeconds(run!.runtime_ms)} · {run!.vehicles_used} vehicles
            </div>
          </div>
        ))}
      </div>

      <div className="border-t border-line bg-surface-2/40 px-4 py-3 text-[11.5px] leading-relaxed text-ink-dim">
        {comparable ? (
          <>
            On this scenario VA-QPSO is{' '}
            <span
              className={
                (ours!.total_cost - base!.total_cost) / base!.total_cost < 0
                  ? 'text-green'
                  : 'text-red'
              }
            >
              {fmtPct(
                Math.abs((ours!.total_cost - base!.total_cost) / base!.total_cost),
              )}{' '}
              {(ours!.total_cost - base!.total_cost) / base!.total_cost < 0
                ? 'lower'
                : 'higher'}{' '}
              cost
            </span>{' '}
            and <span className="text-amber">{(ours!.runtime_ms / base!.runtime_ms).toFixed(1)}× slower</span>.
            Standard benchmarks tell the other half of the story — see the
            Benchmark Lab.
          </>
        ) : (
          <>
            Measured on the live backend by OR-Tools: first-solution{' '}
            <code className="text-[10.5px] text-ink">PATH_CHEAPEST_ARC</code> plus{' '}
            <code className="text-[10.5px] text-ink">GUIDED_LOCAL_SEARCH</code> over a
            CVRP cost matrix. Only this solver has returned a result so far, so there
            is nothing to compare it against yet.
          </>
        )}
      </div>
    </div>
  )
}
