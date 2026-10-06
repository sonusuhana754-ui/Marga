import { Download } from 'lucide-react'
import type { BenchmarkResponse } from '@/types/api'
import { fmtInt, fmtSeconds } from '@/lib/format'
import { Button } from '@/components/ui/controls'
import { solverLabel } from './solverMeta'

export function ResultsTable({ data }: { data: BenchmarkResponse }) {
  const rows = [...data.results].sort((a, b) => a.gap_pct - b.gap_pct)
  const bestId = rows.find((r) => r.feasible)?.solver_id

  const downloadCsv = () => {
    const header =
      'scenario_id,best_known,repeats,solver,cost_mean,cost_best,gap_pct,feasible,runtime_ms_mean,runtime_ms_max'
    const lines = rows.map((r) =>
      [
        data.scenario_id,
        data.best_known,
        data.repeats,
        r.solver_id,
        r.cost,
        r.best_cost,
        r.gap_pct,
        r.feasible,
        r.runtime_ms_mean,
        r.runtime_ms_max,
      ].join(','),
    )
    const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `marga-benchmark-${data.scenario_id}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="label-mono">
          Results · {data.repeats} run{data.repeats === 1 ? '' : 's'} each · best{' '}
          {fmtInt(data.best_known)}
        </span>
        <Button variant="ghost" onClick={downloadCsv} className="!px-2.5 !py-1 !text-[11px]">
          <Download className="h-3 w-3" />
          CSV
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] text-[12px]">
          <thead>
            <tr className="border-b border-line text-[10px] uppercase tracking-wide text-ink-mute">
              <th className="px-4 py-2 text-left font-medium">Solver</th>
              <th className="px-4 py-2 text-right font-medium">Cost (mean)</th>
              <th className="px-4 py-2 text-right font-medium">Best run</th>
              <th className="px-4 py-2 text-right font-medium">Gap</th>
              <th className="px-4 py-2 text-right font-medium">Runtime</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr
                key={r.solver_id}
                className={`border-b border-line/60 ${r.solver_id === 'va_qpso' ? 'bg-marga-wash/40' : ''}`}
              >
                <td className="px-4 py-2 font-medium text-ink">
                  {r.solver_id === bestId && (
                    <span className="mr-1.5 text-[10px] text-green">best</span>
                  )}
                  {solverLabel(r.solver_id)}
                  {!r.feasible && (
                    <span className="ml-1.5 text-[10px] text-amber">infeasible</span>
                  )}
                </td>
                <td className="tnum px-4 py-2 text-right text-ink-dim">{fmtInt(r.cost)}</td>
                <td className="tnum px-4 py-2 text-right text-ink-mute">{fmtInt(r.best_cost)}</td>
                <td className="tnum px-4 py-2 text-right text-ink-dim">
                  {r.feasible ? `${r.gap_pct.toFixed(1)}%` : '—'}
                </td>
                <td className="tnum px-4 py-2 text-right text-ink-mute">
                  {fmtSeconds(r.runtime_ms_mean)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.some((r) => r.violations.length > 0) && (
        <div className="border-t border-line px-4 py-2 text-[10px] text-amber">
          {rows
            .filter((r) => r.violations.length > 0)
            .map((r) => `${solverLabel(r.solver_id)}: ${r.violations.join('; ')}`)
            .join(' · ')}
        </div>
      )}
    </div>
  )
}