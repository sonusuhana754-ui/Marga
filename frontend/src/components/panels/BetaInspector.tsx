import { useMemo } from 'react'
import { Line, LineChart, ReferenceLine, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import type { BetaPoint, OptimizeResponse } from '@/types/api'
import { fmtFixed } from '@/lib/format'
import { C } from '@/lib/palette'

interface BetaInspectorProps {
  /** Measured β, one point per iteration, from the run's own diagnostics. */
  series: BetaPoint[]
  run: OptimizeResponse
}

/**
 * β against iteration, straight from `solver_diagnostics.beta_history`.
 *
 * There is no per-iteration σ² on the wire, so none is drawn: the volatility
 * series the old version charted was a fixture. What this shows is what the
 * solver actually used, and the footer states whether a traffic feed was
 * reaching it.
 */
export function BetaInspector({ series, run }: BetaInspectorProps) {
  const d = run.diagnostics
  const range = d.beta_range ?? []
  const betaMin = range[0]
  const betaMax = range[1]
  const mean = d.mean_beta
  const hasSignal = d.volatility_signal === true

  const data = useMemo(() => series, [series])

  return (
    <div className="panel w-full overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-2.5">
        <span className="label-mono">β per iteration · measured</span>
        <span className="text-[10px] font-medium text-ink-mute">
          {d.beta_mode === 'fixed' ? 'fixed-β arm' : 'adaptive'}
        </span>
      </div>

      <div className="px-2 pt-3">
        <ResponsiveContainer width="100%" height={132}>
          <LineChart data={data} margin={{ top: 4, right: 6, bottom: 0, left: -8 }}>
            <XAxis
              dataKey="iteration"
              type="number"
              domain={[0, 'dataMax']}
              stroke={C.line}
              tick={{ fill: C.inkMute, fontSize: 9 }}
              tickLine={false}
              minTickGap={40}
            />
            <YAxis
              domain={
                betaMin !== undefined && betaMax !== undefined && betaMax > betaMin
                  ? [betaMin - 0.05, betaMax + 0.05]
                  : ['auto', 'auto']
              }
              stroke={C.line}
              tick={{ fill: C.inkMute, fontSize: 9 }}
              tickLine={false}
              width={34}
            />
            {betaMin !== undefined && (
              <ReferenceLine
                y={betaMin}
                stroke={C.inkMute}
                strokeDasharray="3 3"
                strokeWidth={1}
              />
            )}
            {betaMax !== undefined && (
              <ReferenceLine
                y={betaMax}
                stroke={C.inkMute}
                strokeDasharray="3 3"
                strokeWidth={1}
              />
            )}
            <Line
              dataKey="beta"
              stroke={C.marga}
              strokeWidth={2}
              dot={series.length <= 40 ? { r: 1.5 } : false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="flex items-center justify-between px-4 pb-2 pt-1 text-[11px]">
        <span className="flex items-center gap-1.5 text-marga">
          <span className="h-1.5 w-3 rounded-full bg-marga" /> β{' '}
          {fmtFixed(series.at(-1)?.beta ?? 0, 2)} last
        </span>
        <span className="text-ink-mute">mean {fmtFixed(mean ?? 0, 2)}</span>
        <span className="text-ink-mute">
          floor {fmtFixed(betaMin ?? 0, 2)} · ceiling {fmtFixed(betaMax ?? 0, 2)}
        </span>
      </div>

      <p className="border-t border-line bg-surface-2/40 px-4 py-2.5 text-[11px] leading-relaxed text-ink-dim">
        {d.volatility_signal === false ? (
          <>
            No traffic feed reaches this run, so the rolling volatility window is
            empty and β sits at its floor — the solver degraded to exploitation
            rather than inventing a signal. `volatility_signal: false` in the
            response says so.
          </>
        ) : hasSignal ? (
          <>
            β is derived per particle from the rolling variance of the traffic
            observations on the edges its route covers. Each point here is the
            swarm mean for that iteration, as the solver used it.
          </>
        ) : (
          <>
            β is reported by the solver. When no traffic feed reaches it the
            window is empty and β stays at its floor, which is what
            `volatility_signal: false` marks.
          </>
        )}
      </p>
    </div>
  )
}
