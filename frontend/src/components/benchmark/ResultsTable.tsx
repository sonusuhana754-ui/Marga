import { Download } from 'lucide-react'
import type { BenchmarkResponse } from '@/types/api'
import { fmtInt, fmtSeconds } from '@/lib/format'
import { Button } from '@/components/ui/controls'
import { solverLabel } from './solverMeta'

export function ResultsTable({ data }: { data: BenchmarkResponse }) {
  const rows = [...data.results].sort((a, b) => a.gap_pct - b.gap_pct)

  const downloadCsv = () => {
    const header = 'instance,best_known,solver,cost,gap_pct,runtime_ms'
    const lines = rows.map(
      (r) =>
        `${data.instance},${data.best_known},${r.solver},${r.cost},${r.gap_pct},${r.runtime_ms}`,
    )
    const blob = new Blob([[header, ...lines].join('\n')], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `marga-benchmark-${data.instance}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="label-mono">
          Results · best-known {fmtInt(data.best_known)}
        </span>
        <Button variant="ghost" onClick={downloadCsv} className="!px-2.5 !py-1 !text-[11px]">
          <Download className="h-3 w-3" />
          CSV
        </Button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] text-[12px]">
          <thead>
            <tr className="border-b border-line text-[10px] uppercase tracking-wide text-ink-mute">
              <th className="px-4 py-2 text-left font-medium">Solver</th>
              <th className="px-4 py-2 text-right font-medium">Cost</th>
              <th className="px-4 py-2 text-right font-medium">Gap</th>
              <th className="px-4 py-2 text-right font-medium">Runtime</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr
                key={r.solver}
                className={`border-b border-line/60 ${r.solver === 'va_qpso' ? 'bg-marga-wash/40' : ''}`}
              >
                <td className="px-4 py-2 font-medium text-ink">
                  {i === 0 && <span className="mr-1.5 text-[10px] text-green">best</span>}
                  {solverLabel(r.solver)}
                </td>
                <td className="tnum px-4 py-2 text-right text-ink-dim">{fmtInt(r.cost)}</td>
                <td className="tnum px-4 py-2 text-right text-ink-dim">{r.gap_pct.toFixed(1)}%</td>
                <td className="tnum px-4 py-2 text-right text-ink-mute">{fmtSeconds(r.runtime_ms)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
