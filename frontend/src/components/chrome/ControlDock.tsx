import { useState } from 'react'
import { Crosshair, Loader2, MapPin, RotateCw, Sparkles, Waves } from 'lucide-react'
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

/** Live speed line, or the honest reason there isn't one. */
function TrafficLine() {
  const { traffic, trafficLoading, trafficError, refreshTraffic } = useDemo()

  if (trafficError) {
    return (
      <p className="text-[11px] leading-relaxed text-amber">
        traffic read failed · {trafficError}
      </p>
    )
  }
  if (trafficLoading) {
    return (
      <p className="flex items-center gap-1.5 text-[11px] text-ink-mute">
        <Loader2 className="h-3 w-3 animate-spin" /> probing live traffic…
      </p>
    )
  }
  if (!traffic) return null

  if (!traffic.configured) {
    return (
      <p className="text-[11px] leading-relaxed text-ink-mute">
        {traffic.detail ?? 'No traffic feed configured — β stays at its floor.'}
      </p>
    )
  }
  const s = traffic.snapshot
  if (!s) {
    return (
      <p className="text-[11px] leading-relaxed text-ink-mute">
        {traffic.detail ?? 'Traffic feed returned no readings.'}
      </p>
    )
  }
  const time = new Date(s.observed_at).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
  return (
    <button
      type="button"
      onClick={() => void refreshTraffic()}
      className="flex w-full items-center justify-between text-left text-[11px] text-ink-dim transition-colors hover:text-ink"
      title="Re-probe live traffic"
    >
      <span className="flex items-center gap-1.5">
        <Waves className="h-3 w-3 text-marga" />
        <span className="label-mono !text-[9.5px] !text-marga">{s.source} live</span>
        <span className="tnum">
          {s.mean_current_kmh.toFixed(0)} / {s.mean_free_flow_kmh.toFixed(0)} km/h
        </span>
      </span>
      <span className="tnum flex items-center gap-1 text-ink-mute">
        {time}
        <RotateCw className="h-3 w-3" />
      </span>
    </button>
  )
}

export function ControlDock() {
  const {
    mode,
    setMode,
    solver,
    setSolver,
    status,
    error,
    optimize,
    activeRun,
    reset,
    area,
    areaLoading,
    areaError,
    picking,
    setPicking,
    loadAreaByName,
  } = useDemo()
  const [place, setPlace] = useState('')

  const submitPlace = () => {
    const value = place.trim()
    if (!value) return
    void loadAreaByName(value)
  }

  return (
    <div className="panel w-[272px] overflow-hidden">
      <div className="space-y-2 px-4 py-3.5">
        <span className="label-mono">Problem</span>
        <Segmented<Mode> options={MODE_OPTIONS} value={mode} onChange={setMode} />
      </div>

      <div className="space-y-2 border-t border-line px-4 py-3.5">
        <div className="flex items-center justify-between">
          <span className="label-mono">Road network</span>
          <button
            type="button"
            onClick={() => setPicking(!picking)}
            className={`flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium transition-colors ${
              picking
                ? 'border-marga/60 text-marga'
                : 'border-line text-ink-dim hover:text-ink'
            }`}
            title="Click anywhere on the map to load its road network"
          >
            <Crosshair className="h-3 w-3" />
            {picking ? 'click the map' : 'pick a place'}
          </button>
        </div>

        {area ? (
          <div className="space-y-1.5">
            <div className="flex items-start gap-1.5 text-[12px] text-ink">
              <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-marga" />
              <span className="leading-snug">{area.label}</span>
            </div>
            <p className="tnum text-[11px] text-ink-mute">
              {fmtInt(area.nodes)} junctions · {fmtInt(area.edges)} roads ·{' '}
              {area.total_length_km.toFixed(1)} km
            </p>
            <TrafficLine />
          </div>
        ) : (
          <div className="space-y-1.5">
            <p className="text-[11.5px] leading-relaxed text-ink-dim">
              None loaded yet. Pick a point on the map, or name a place — the
              backend fetches its real OSM road network.
            </p>
            <div className="flex gap-1.5">
              <input
                value={place}
                onChange={(e) => setPlace(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') submitPlace()
                }}
                placeholder="Indiranagar, Bengaluru"
                className="min-w-0 flex-1 rounded-md border border-line bg-surface-2 px-2 py-1 text-[11.5px] text-ink placeholder:text-ink-mute focus:border-marga/60 focus:outline-none"
              />
              <button
                type="button"
                onClick={submitPlace}
                disabled={areaLoading || !place.trim()}
                className="rounded-md border border-line px-2 py-1 text-[11px] font-medium text-ink transition-colors hover:text-marga disabled:opacity-40"
              >
                {areaLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Load'}
              </button>
            </div>
          </div>
        )}

        {areaLoading && (
          <p className="flex items-center gap-1.5 text-[11px] text-ink-mute">
            <Loader2 className="h-3 w-3 animate-spin" /> downloading road network…
          </p>
        )}
        {areaError && (
          <p className="break-words text-[11px] leading-relaxed text-red">{areaError}</p>
        )}
      </div>

      {mode === 'fleet' && (
        <div className="space-y-3 border-t border-line px-4 py-3.5">
          {status === 'idle' && (
            <>
              <p className="text-[12px] leading-relaxed text-ink-dim">
                {area
                  ? `${area.label}: stops drawn from real junctions. Assignment and ordering — the part exact solvers can't scale.`
                  : 'Loads the road network first, then solves the fleet problem on it.'}
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

          {status === 'error' && (
            <div className="space-y-2">
              <p className="break-words text-[12px] leading-relaxed text-red">
                {error || 'The backend did not return a result.'}
              </p>
              <Button className="w-full" onClick={optimize}>
                <RotateCw className="h-3.5 w-3.5" />
                Retry
              </Button>
            </div>
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
              <TrafficLine />
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
          restriction, computed on the loaded road network. Details below.
        </div>
      )}
    </div>
  )
}
