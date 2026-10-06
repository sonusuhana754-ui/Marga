import { useEffect } from 'react'
import { MapCanvas } from '@/components/map/MapCanvas'
import { RouteLayer } from '@/components/map/RouteLayer'
import { BlockedEdges } from '@/components/map/BlockedEdges'
import { FleetLayer } from '@/components/map/FleetLayer'
import { VehicleMarkers } from '@/components/map/VehicleMarkers'
import { Waypoints } from '@/components/map/Waypoints'
import { AreaFramer, AreaPicker } from '@/components/map/AreaPicker'
import { TopBar } from '@/components/chrome/TopBar'
import { ControlDock } from '@/components/chrome/ControlDock'
import { TransportControls } from '@/components/chrome/TransportControls'
import { StatusIndicator } from '@/components/chrome/StatusIndicator'
import { RouteCompare } from '@/components/panels/RouteCompare'
import { SolverResult } from '@/components/panels/SolverResult'
import { VehiclePanel } from '@/components/panels/VehiclePanel'
import { WhyRoute } from '@/components/panels/WhyRoute'
import { BetaInspector } from '@/components/panels/BetaInspector'
import { ImpactStrip } from '@/components/panels/ImpactStrip'
import { BenchmarkView } from '@/components/benchmark/BenchmarkView'
import { DemoRunner } from '@/components/demo/DemoRunner'
import { useDemo } from '@/state/demoStore'
import { useSimClock } from '@/state/simClock'
import { DEFAULT_PROFILE, AREA } from '@/config'
import { DEPOT, STOPS } from '@/scene'
import type { LngLat } from '@/types/api'

export function Dashboard() {
  const {
    view,
    guided,
    mode,
    status,
    solver,
    runs,
    activeRun,
    betaSeries,
    area,
    single,
    singleError,
    retrySingle,
    selectedVehicle,
    selectVehicle,
  } = useDemo()
  const clock = useSimClock()

  // Depot/stops on the map. The backend's own points win — they are what the
  // solver actually routed on. Scene pins appear only while no area exists:
  // once a real graph is loaded, hand-placed pins would misrepresent it.
  const scenarioPoints = activeRun?.points ?? []
  const backendDepot = scenarioPoints.find((p) => p.is_depot)
  const backendStops = scenarioPoints.filter((p) => !p.is_depot)
  const waypoints =
    backendDepot && backendStops.length > 0
      ? {
          depot: [backendDepot.lng, backendDepot.lat] as LngLat,
          stops: backendStops.map((p) => [p.lng, p.lat] as LngLat),
        }
      : area
        ? null
        : { depot: DEPOT, stops: STOPS }

  const fleetReady = mode === 'fleet' && status === 'ready' && activeRun !== null
  const selectedRoute =
    fleetReady && selectedVehicle !== null
      ? activeRun!.routes.find((r) => r.vehicle_id === selectedVehicle)
      : undefined

  // Savings are a difference between two measured runs. A run where our solver
  // did not beat the baseline saves nothing, and a strip of zeros would read
  // like a claim — so it is shown only when something was actually saved.
  const measured = runs.va_qpso?.impact
  const impact =
    measured && measured.measured && measured.distance_saved_m + measured.time_saved_s > 0
      ? measured
      : null

  useEffect(() => {
    if (fleetReady && activeRun) {
      const dur = activeRun.routes.reduce((m, r) => Math.max(m, r.timestamps.at(-1) ?? 0), 0)
      clock.setDuration(dur)
      clock.seek(0)
    } else {
      clock.setDuration(0)
    }
  }, [clock, fleetReady, activeRun])

  return (
    <div className="relative h-dvh w-dvw overflow-hidden bg-bg text-ink">
      <MapCanvas>
        {mode === 'single' && single && (
          <>
            <RouteLayer best={single.best.path} alternative={single.unconstrained.path} />
            <BlockedEdges edges={single.blocked_edges} />
          </>
        )}
        {fleetReady && (
          <>
            <FleetLayer
              routes={activeRun!.routes}
              selected={selectedVehicle}
              onSelect={selectVehicle}
            />
            <VehicleMarkers routes={activeRun!.routes} selected={selectedVehicle} />
          </>
        )}
        {waypoints && <Waypoints depot={waypoints.depot} stops={waypoints.stops} />}
        <AreaPicker />
        <AreaFramer />
      </MapCanvas>

      {view === 'benchmark' && <BenchmarkView />}

      <TopBar />

      {guided && <DemoRunner />}

      {view === 'live' && (
        <div className="pointer-events-none absolute inset-0 z-10">
          <div className="pointer-events-auto absolute left-4 top-20 flex w-[272px] flex-col gap-3">
            <ControlDock />
            {mode === 'single' && single && (
              <RouteCompare route={single} profile={DEFAULT_PROFILE} />
            )}
            {mode === 'single' && !single && (
              <div className="panel w-[300px] px-4 py-3">
                <div className="label-mono">Single vehicle</div>
                <p className="mt-1.5 text-[12px] leading-relaxed text-ink-dim">
                  {singleError ? (
                    <>
                      The backend returned no route:
                      <span className="mt-1 block break-words text-ink-mute">
                        {singleError}
                      </span>
                      <button
                        type="button"
                        onClick={() => void retrySingle()}
                        className="mt-2 rounded-md border border-line px-2.5 py-1 text-[11px] font-medium text-ink transition-colors hover:text-marga"
                      >
                        Load OSM graph &amp; retry
                      </button>
                    </>
                  ) : (
                    'Asking the backend for the route…'
                  )}
                </p>
              </div>
            )}
            {fleetReady && <SolverResult runs={runs} active={solver} />}
          </div>

          {mode === 'fleet' && status !== 'idle' && (
            <div className="pointer-events-auto absolute left-1/2 top-4 -translate-x-1/2">
              <StatusIndicator />
            </div>
          )}

          {fleetReady && (betaSeries || selectedRoute) && (
            <div className="pointer-events-auto absolute right-4 top-20 flex max-h-[calc(100dvh-8rem)] w-[300px] flex-col gap-3 overflow-y-auto pb-2">
              {betaSeries && betaSeries.length > 0 && (
                <BetaInspector series={betaSeries} run={activeRun!} />
              )}
              {selectedRoute && (
                <>
                  <VehiclePanel
                    route={selectedRoute}
                    profile={DEFAULT_PROFILE}
                    onClose={() => selectVehicle(null)}
                  />
                  <WhyRoute route={selectedRoute} />
                </>
              )}
            </div>
          )}

          <div className="pointer-events-auto absolute bottom-4 left-1/2 flex w-[min(680px,calc(100vw-2rem))] -translate-x-1/2 flex-col items-center gap-3">
            {fleetReady && <TransportControls />}
            {impact && <ImpactStrip impact={impact} />}
          </div>
        </div>
      )}

      {import.meta.env.DEV && (
        <div className="pointer-events-none absolute bottom-1.5 left-4 z-10">
          <span className="label-mono !text-[9px] !text-ink-mute/50">
            dev · {area?.label ?? AREA.label} · world view
          </span>
        </div>
      )}
    </div>
  )
}
