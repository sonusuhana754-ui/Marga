import { MapCanvas } from '@/components/map/MapCanvas'
import { RouteLayer } from '@/components/map/RouteLayer'
import { BlockedEdges } from '@/components/map/BlockedEdges'
import { FleetLayer } from '@/components/map/FleetLayer'
import { VehicleMarkers } from '@/components/map/VehicleMarkers'
import { Waypoints } from '@/components/map/Waypoints'
import { TopBar } from '@/components/chrome/TopBar'
import { ControlDock } from '@/components/chrome/ControlDock'
import { TransportControls } from '@/components/chrome/TransportControls'
import { RouteCompare } from '@/components/panels/RouteCompare'
import { SolverResult } from '@/components/panels/SolverResult'
import { VehiclePanel } from '@/components/panels/VehiclePanel'
import { ImpactStrip } from '@/components/panels/ImpactStrip'
import { useEffect } from 'react'
import { useDemo } from '@/state/demoStore'
import { useSimClock } from '@/state/simClock'
import { DEFAULT_PROFILE } from '@/config'
import { DEPOT, STOPS, mockImpactSample } from '@/mocks'

export function Dashboard() {
  const { mode, status, solver, runs, activeRun, single, selectedVehicle, selectVehicle } =
    useDemo()
  const clock = useSimClock()

  const fleetReady = mode === 'fleet' && status === 'ready' && activeRun !== null

  // keep the sim clock in step with the active run
  useEffect(() => {
    if (fleetReady && activeRun) {
      const dur = activeRun.routes.reduce(
        (m, r) => Math.max(m, r.timestamps.at(-1) ?? 0),
        0,
      )
      clock.setDuration(dur)
      clock.seek(0)
    } else {
      clock.setDuration(0)
    }
  }, [clock, fleetReady, activeRun])
  const selectedRoute =
    fleetReady && selectedVehicle !== null
      ? activeRun!.routes.find((r) => r.vehicle_id === selectedVehicle)
      : undefined

  const impact = mode === 'single' ? mockImpactSample : (runs.va_qpso?.impact ?? null)

  return (
    <div className="relative h-dvh w-dvw overflow-hidden bg-bg text-ink">
      <MapCanvas>
        {mode === 'single' && (
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
        <Waypoints depot={DEPOT} stops={STOPS} />
      </MapCanvas>

      <TopBar />

      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="pointer-events-auto absolute left-4 top-20 flex w-[272px] flex-col gap-3">
          <ControlDock />
          {mode === 'single' && <RouteCompare route={single} profile={DEFAULT_PROFILE} />}
          {fleetReady && <SolverResult runs={runs} active={solver} />}
        </div>

        {selectedRoute && (
          <div className="pointer-events-auto absolute right-4 top-20">
            <VehiclePanel
              route={selectedRoute}
              profile={DEFAULT_PROFILE}
              onClose={() => selectVehicle(null)}
            />
          </div>
        )}

        <div className="pointer-events-auto absolute bottom-4 left-1/2 flex w-[min(680px,calc(100vw-2rem))] -translate-x-1/2 flex-col items-center gap-3">
          {fleetReady && <TransportControls />}
          {impact && <ImpactStrip impact={impact} />}
        </div>
      </div>

      <div className="pointer-events-none absolute bottom-1.5 left-4 z-10">
        <span className="label-mono !text-[9px] !text-ink-mute/60">
          MARGA · block 4 · mock data · area not locked
        </span>
      </div>
    </div>
  )
}
