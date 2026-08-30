import { useMemo } from 'react'
import { Bar, BarChart, Cell, LabelList, XAxis, YAxis, ResponsiveContainer } from 'recharts'
import type { BenchmarkResult } from '@/types/api'
import { C } from '@/lib/palette'
import { solverColor, solverLabel } from './solverMeta'

/** Gap to best-known, sorted best-first. Not rearranged to flatter VA-QPSO. */
export function GapChart({ results }: { results: BenchmarkResult[] }) {
  const data = useMemo(
    () =>
      [...results]
        .sort((a, b) => a.gap_pct - b.gap_pct)
        .map((r) => ({
          name: solverLabel(r.solver),
          gap: r.gap_pct,
          color: solverColor(r.solver),
          ours: r.solver === 'va_qpso',
        })),
    [results],
  )

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="label-mono">Gap to best-known</span>
        <span className="text-[10px] text-ink-mute">sorted best-first · lower is better</span>
      </div>
      <div className="px-3 py-3">
        <ResponsiveContainer width="100%" height={data.length * 34 + 10}>
          <BarChart data={data} layout="vertical" margin={{ left: 4, right: 44, top: 0, bottom: 0 }}>
            <XAxis type="number" hide domain={[0, 'dataMax']} />
            <YAxis
              type="category"
              dataKey="name"
              width={66}
              stroke={C.line}
              tick={{ fill: C.inkDim, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <Bar dataKey="gap" radius={[0, 3, 3, 0]} barSize={16} isAnimationActive={false}>
              {data.map((d) => (
                <Cell
                  key={d.name}
                  fill={d.color}
                  fillOpacity={d.ours ? 1 : 0.5}
                  stroke={d.ours ? d.color : 'transparent'}
                />
              ))}
              <LabelList
                dataKey="gap"
                position="right"
                formatter={(v: unknown) => `${Number(v).toFixed(1)}%`}
                fill={C.inkDim}
                fontSize={11}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
