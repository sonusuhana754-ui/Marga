import { useMemo } from 'react'
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  XAxis,
  YAxis,
} from 'recharts'
import { Eye, EyeOff } from 'lucide-react'
import type { StreamTick } from '@/types/api'
import { BETA_CEILING } from '@/config'
import { TICK_SECONDS } from '@/mocks/stream'
import { fmtClock, fmtFixed } from '@/lib/format'
import { C } from '@/lib/palette'

interface BetaInspectorProps {
  series: StreamTick[]
  current: StreamTick | null
  overlayOn: boolean
  onToggleOverlay: () => void
}

export function BetaInspector({ series, current, overlayOn, onToggleOverlay }: BetaInspectorProps) {
  // the zone that gets most volatile anywhere in the run
  const hotZoneId = useMemo(() => {
    let best = ''
    let peak = -1
    for (const t of series) {
      for (const z of t.zone_volatility) {
        if (z.sigma_sq > peak) {
          peak = z.sigma_sq
          best = z.zone_id
        }
      }
    }
    return best
  }, [series])

  const data = useMemo(
    () =>
      series.map((t) => {
        const z = t.zone_volatility.find((v) => v.zone_id === hotZoneId)
        return { s: t.tick * TICK_SECONDS, sigma: z?.sigma_sq ?? 0, beta: z?.beta ?? 1 }
      }),
    [series, hotZoneId],
  )

  const cursorX = current ? current.tick * TICK_SECONDS : 0
  const now = current?.zone_volatility.find((v) => v.zone_id === hotZoneId)
  const zones = current?.zone_volatility ?? []

  return (
    <div className="panel w-full overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="label-mono">β vs volatility · {hotZoneId}</span>
        <button
          type="button"
          onClick={onToggleOverlay}
          className={`flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
            overlayOn
              ? 'border-marga/50 text-marga'
              : 'border-line text-ink-mute hover:text-ink-dim'
          }`}
        >
          {overlayOn ? <Eye className="h-3 w-3" /> : <EyeOff className="h-3 w-3" />}
          zone heat map
        </button>
      </div>

      <div className="px-2 pt-3">
        <ResponsiveContainer width="100%" height={132}>
          <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: -8 }}>
            <XAxis
              dataKey="s"
              type="number"
              domain={[0, 'dataMax']}
              tickFormatter={(v) => fmtClock(v)}
              stroke={C.line}
              tick={{ fill: C.inkMute, fontSize: 9 }}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              yAxisId="beta"
              domain={[0.9, 1.9]}
              stroke={C.line}
              tick={{ fill: C.inkMute, fontSize: 9 }}
              tickLine={false}
              width={26}
            />
            <YAxis yAxisId="sigma" domain={[0, 1]} hide />
            <ReferenceLine
              yAxisId="beta"
              y={BETA_CEILING}
              stroke={C.inkMute}
              strokeDasharray="3 3"
              strokeWidth={1}
            />
            <ReferenceLine yAxisId="beta" x={cursorX} stroke={C.ink} strokeWidth={1} />
            <Line
              yAxisId="sigma"
              dataKey="sigma"
              stroke={C.amber}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              yAxisId="beta"
              dataKey="beta"
              stroke={C.marga}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-between px-4 pb-2 pt-1 text-[11px]">
        <span className="flex items-center gap-1.5 text-amber">
          <span className="h-1.5 w-3 rounded-full bg-amber" /> σ² {fmtFixed(now?.sigma_sq ?? 0, 2)}
        </span>
        <span className="flex items-center gap-1.5 text-marga">
          <span className="h-1.5 w-3 rounded-full bg-marga" /> β {fmtFixed(now?.beta ?? 1, 2)}
        </span>
        <span className="text-ink-mute">ceiling {BETA_CEILING}</span>
      </div>

      <div className="flex gap-1.5 border-t border-line px-4 py-2.5">
        {zones.map((z) => {
          const hot = z.sigma_sq
          const color =
            hot > 0.5 ? C.red : hot > 0.25 ? C.amber : C.margaDeep
          return (
            <div key={z.zone_id} className="flex flex-1 flex-col items-center gap-1">
              <span
                className="h-2 w-full rounded-full"
                style={{ background: color, opacity: 0.35 + Math.min(hot, 1) * 0.65 }}
              />
              <span className="label-mono !text-[8px] !tracking-normal">
                {z.zone_id.replace('z_', '')}
              </span>
            </div>
          )
        })}
      </div>

      <p className="border-t border-line bg-surface-2/40 px-4 py-2.5 text-[11px] leading-relaxed text-ink-dim">
        β and σ² come straight from the solver, one value per zone per tick.
        Here they track each other as {hotZoneId} congests. What the coupling
        means is the paper’s claim — this view just shows it happening.
      </p>
    </div>
  )
}
