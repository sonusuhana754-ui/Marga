import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import type { BenchmarkResult } from '@/types/api'
import { C } from '@/lib/palette'
import { fmtInt } from '@/lib/format'
import { solverColor, solverLabel } from './solverMeta'

/**
 * Best cost per iteration, one line per solver that reports a trace.
 *
 * Solvers without a measured trace are named in the footnote instead of being
 * given a curve. OR-Tools has no per-iteration hook, so plotting one for it would
 * mean inventing its search path — the single most misleading thing this chart
 * could do.
 */
export function ConvergenceChart({ results }: { results: BenchmarkResult[] }) {
  const { data, solvers, missing } = useMemo(() => {
    const traced = results.filter((r) => r.convergence.length > 0)
    const maxIter = Math.max(1, ...traced.map((r) => r.convergence.length))
    const rows: Record<string, number>[] = []
    for (let i = 0; i < maxIter; i++) {
      const row: Record<string, number> = { iteration: i }
      for (const r of traced) {
        const pt = r.convergence[i] ?? r.convergence[r.convergence.length - 1]
        if (pt) row[r.solver_id] = pt.best_cost
      }
      rows.push(row)
    }
    return {
      data: rows,
      solvers: traced.map((r) => r.solver_id),
      missing: results.filter((r) => r.convergence.length === 0).map((r) => solverLabel(r.solver_id)),
    }
  }, [results])

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="label-mono">Convergence</span>
        <span className="text-[10px] text-ink-mute">measured best cost per iteration</span>
      </div>
      <div className="px-3 py-3">
        <ResponsiveContainer width="100%" height={210}>
          <LineChart data={data} margin={{ top: 4, right: 12, bottom: 0, left: 4 }}>
            <CartesianGrid stroke={C.line} strokeOpacity={0.4} vertical={false} />
            <XAxis
              dataKey="iteration"
              stroke={C.line}
              tick={{ fill: C.inkMute, fontSize: 9 }}
              tickLine={false}
            />
            <YAxis
              stroke={C.line}
              tick={{ fill: C.inkMute, fontSize: 9 }}
              tickLine={false}
              width={44}
              tickFormatter={(v) => fmtInt(v)}
              domain={['dataMin', 'dataMax']}
            />
            {solvers.map((s) => (
              <Line
                key={s}
                dataKey={s}
                stroke={solverColor(s)}
                strokeWidth={s === 'va_qpso' ? 2.4 : 1.5}
                strokeOpacity={s === 'va_qpso' ? 1 : 0.7}
                dot={false}
                isAnimationActive={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <div className="flex flex-wrap gap-x-3 gap-y-1 px-1 pt-1">
          {solvers.map((s) => (
            <span key={s} className="flex items-center gap-1.5 text-[10px] text-ink-mute">
              <span className="h-1.5 w-3 rounded-full" style={{ background: solverColor(s) }} />
              {solverLabel(s)}
            </span>
          ))}
        </div>
        {missing.length > 0 && (
          <p className="px-1 pt-1.5 text-[10px] text-ink-mute">
            No per-iteration trace reported by: {missing.join(', ')}. Not drawn.
          </p>
        )}
      </div>
    </div>
  )
}