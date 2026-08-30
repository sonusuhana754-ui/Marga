import { Loader2, RotateCw, Sparkles } from 'lucide-react'
import { useDemo } from '@/state/demoStore'
import { SOLVERS } from '@/config'
import { fmtInt } from '@/lib/format'
import { Button, Segmented } from '@/components/ui/controls'
import type { Mode } from '@/state/demoStore'
import type { SolverId } from '@/types/api'

const MODE_OPTIONS: { value: Mode; label: string; hint: string }[] = [
  { value: 'single', label: 'Single vehicle', hint: 'One truck, origin to destination' },
  { value: 'fleet', label: 'Fleet', hint: 'Many vehicles, many stops — the NP-hard problem' },
]

const SOLVER_OPTIONS = SOLVERS.map((s) => ({ value: s.id, label: s.label }))

export function ControlDock() {
  const { mode, setMode, solver, setSolver, status, optimize, activeRun, reset } = useDemo()

  return (
    <div className="panel w-[272px] overflow-hidden">
      <div className="space-y-2 px-4 py-3.5">
        <span className="label-mono">Problem</span>
        <Segmented<Mode> options={MODE_OPTIONS} value={mode} onChange={setMode} />
      </div>

      {mode === 'fleet' && (
        <div className="space-y-3 border-t border-line px-4 py-3.5">
          {status === 'idle' && (
            <>
              <p className="text-[12px] leading-relaxed text-ink-dim">
                20 stops, 2 vehicles from the Koramangala depot. Assignment and
                ordering — the part exact solvers can’t scale.
              </p>
              <Button className="w-full" onClick={optimize}>
                <Sparkles className="h-3.5 w-3.5" />
                Optimize routes
              </Button>
            </>
          )}

          {status === 'optimizing' && (
            <Button className="w-full" disabled>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              Optimizing…
            </Button>
          )}

          {status === 'ready' && (
            <>
              <div className="space-y-1.5">
                <span className="label-mono">Solver</span>
                <Segmented<SolverId>
                  options={SOLVER_OPTIONS}
                  value={solver}
                  onChange={setSolver}
                  size="sm"
                />
              </div>
              {activeRun && (
                <div className="flex items-center justify-between rounded-md bg-surface-2/50 px-2.5 py-2 text-[11px]">
                  <span className="text-ink-mute">
                    {activeRun.vehicles_used} vehicles · {(activeRun.total_cost / 1000).toFixed(1)} km
                  </span>
                  <span className="tnum text-ink-dim">
                    {fmtInt(activeRun.runtime_ms)} ms
                  </span>
                </div>
              )}
              <Button variant="ghost" className="w-full" onClick={reset}>
                <RotateCw className="h-3.5 w-3.5" />
                Reset
              </Button>
            </>
          )}
        </div>
      )}

      {mode === 'single' && (
        <div className="border-t border-line px-4 py-3 text-[12px] leading-relaxed text-ink-dim">
          Shortest path vs the lowest-cost route that clears every vehicle
          restriction. Details below.
        </div>
      )}
    </div>
  )
}
