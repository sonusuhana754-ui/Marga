import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type {
  BetaPoint,
  LoadedArea,
  LngLat,
  OptimizeResponse,
  RouteResponse,
  SolverId,
} from '@/types/api'
import { runOptimize, runRoute } from '@/api/optimize'
import { fetchTraffic, loadAreaByCenter, loadAreaByPlace } from '@/api/graph'
import { AREA, ASSUMPTIONS, DEFAULT_PROFILE, DEFAULT_SOLVER, SOLVERS } from '@/config'
import { DemoCtx } from './demoStore'
import type { DemoValue, Mode, View } from './demoStore'

/** Measured β per iteration, taken from the solver's own diagnostics. */
function betaSeriesOf(run: OptimizeResponse | null): BetaPoint[] | null {
  const history = run?.diagnostics.beta_history
  if (!history || history.length === 0) return null
  return history.map((beta, iteration) => ({ iteration, beta }))
}

function messageOf(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export function DemoProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<View>('live')
  const [guided, setGuided] = useState(false)
  const [mode, setModeRaw] = useState<Mode>('fleet')
  const [solver, setSolver] = useState<SolverId>(DEFAULT_SOLVER)
  const [status, setStatus] = useState<DemoValue['status']>('idle')
  const [error, setError] = useState('')
  const [runs, setRuns] = useState<Partial<Record<SolverId, OptimizeResponse>>>({})
  const [single, setSingle] = useState<RouteResponse | null>(null)
  const [singleError, setSingleError] = useState<string | null>(null)
  const [selectedVehicle, setSelectedVehicle] = useState<number | null>(null)

  // The loaded OSM area: which roads exist, which key /route is asked about,
  // and where the map flies. Ref + state so async flows never read a stale one.
  const [area, setArea] = useState<LoadedArea | null>(null)
  const [areaLoading, setAreaLoading] = useState(false)
  const [areaError, setAreaError] = useState<string | null>(null)
  const [picking, setPicking] = useState(false)
  const areaRef = useRef<LoadedArea | null>(null)
  const areaErrorRef = useRef<string | null>(null)

  const [traffic, setTraffic] = useState<DemoValue['traffic']>(null)
  const [trafficLoading, setTrafficLoading] = useState(false)
  const [trafficError, setTrafficError] = useState<string | null>(null)

  const refreshTraffic = useCallback(async () => {
    const current = areaRef.current
    if (!current) return
    setTrafficLoading(true)
    setTrafficError(null)
    try {
      setTraffic(await fetchTraffic(current.graph_key))
    } catch (err) {
      const message = messageOf(err)
      setTrafficError(message)
      console.warn('[traffic] unavailable:', message)
    } finally {
      setTrafficLoading(false)
    }
  }, [])

  /** Shared load path: sets loading/error state and returns the area or null. */
  const doLoad = useCallback(
    async (fetcher: () => Promise<LoadedArea>): Promise<LoadedArea | null> => {
      setAreaLoading(true)
      setAreaError(null)
      areaErrorRef.current = null
      try {
        const loaded = await fetcher()
        areaRef.current = loaded
        setArea(loaded)
        setPicking(false)
        // Fresh area → fresh speeds. Failures land in trafficError, not here.
        void refreshTraffic()
        return loaded
      } catch (err) {
        const message = messageOf(err)
        areaErrorRef.current = message
        setAreaError(message)
        console.warn('[graphs/load] failed:', message)
        return null
      } finally {
        setAreaLoading(false)
      }
    },
    [refreshTraffic],
  )

  const loadAreaByPoint = useCallback(
    async (center: LngLat) => {
      await doLoad(() => loadAreaByCenter(center, AREA.dist_m))
    },
    [doLoad],
  )
  const loadAreaByName = useCallback(
    async (place: string) => {
      await doLoad(() => loadAreaByPlace(place))
    },
    [doLoad],
  )

  /** Guarantee an area exists before a request that needs one. */
  const ensureArea = useCallback(async (): Promise<LoadedArea | null> => {
    if (areaRef.current) return areaRef.current
    return doLoad(() => loadAreaByCenter(AREA.center, AREA.dist_m))
  }, [doLoad])

  const optimize = useCallback(async () => {
    setStatus('optimizing')
    setError('')
    setSelectedVehicle(null)

    const ready = await ensureArea()
    if (!ready) {
      setStatus('error')
      setError(areaErrorRef.current || 'Could not load an OSM road graph.')
      return
    }

    const base = {
      city: AREA.id,
      vehicles: 2,
      vehicle_profile: DEFAULT_PROFILE,
      capacity: 100,
      stops: 14,
      seed: 42,
    }
    const wanted = SOLVERS.map((s) => s.id)
    const settled = await Promise.allSettled(
      wanted.map((id) => runOptimize({ ...base, solver: id }, ready)),
    )

    const next: Partial<Record<SolverId, OptimizeResponse>> = {}
    const failures: string[] = []
    settled.forEach((result, i) => {
      if (result.status === 'fulfilled') next[wanted[i]] = result.value
      else {
        const reason = messageOf(result.reason)
        failures.push(`${wanted[i]}: ${reason}`)
        console.warn(`[optimize] ${wanted[i]} failed:`, result.reason)
      }
    })
    setRuns(next)

    if (Object.keys(next).length === 0) {
      setStatus('error')
      setError(failures.join(' · ') || 'No solver returned a result.')
      return
    }
    setStatus('ready')

    // Impact figures are a difference between two solvers, so they only mean
    // something once both have run. With one solver there is no baseline.
    const ours = next.va_qpso
    const baseline = next.ortools
    if (ours && baseline) {
      const legKm = (r: OptimizeResponse) =>
        r.routes.reduce((sum, route) => sum + route.distance_m, 0) / 1000
      const endS = (r: OptimizeResponse) =>
        r.routes.reduce((m, route) => Math.max(m, route.timestamps.at(-1) ?? 0), 0)
      const savedM = Math.max(
        0,
        baseline.routes.reduce((s, r) => s + r.distance_m, 0) -
          ours.routes.reduce((s, r) => s + r.distance_m, 0),
      )
      const km = legKm(baseline) - legKm(ours)
      const fuel = Math.max(0, km) * ASSUMPTIONS.fuelPerKm
      setRuns({
        ...next,
        va_qpso: {
          ...ours,
          impact: {
            time_saved_s: Math.max(0, Math.round(endS(baseline) - endS(ours))),
            fuel_saved_l: Number(fuel.toFixed(1)),
            co2_saved_kg: Number((fuel * ASSUMPTIONS.co2PerLitre).toFixed(1)),
            distance_saved_m: Math.round(savedM),
            // Distance is summed from the two solvers' reported leg distances.
            // Travel time is the modelled clock (fixed 50 km/h), and fuel/CO₂
            // are the stated assumptions applied to that distance.
            measured: true,
          },
        },
      })
    }
  }, [ensureArea])

  /** Single-vehicle route, fetched from the backend. Failures stay visible. */
  const singleRequested = useRef(false)
  const loadSingle = useCallback(async () => {
    if (singleRequested.current) return
    singleRequested.current = true
    setSingleError(null)
    const ready = await ensureArea()
    if (!ready) {
      singleRequested.current = false
      setSingleError(areaErrorRef.current || 'Could not load an OSM road graph.')
      return
    }
    try {
      setSingle(await runRoute(ready))
      setSingleError(null)
    } catch (err) {
      const message = messageOf(err)
      setSingleError(message)
      singleRequested.current = false
      console.warn('[route] unavailable:', message)
    }
  }, [ensureArea])

  /**
   * Re-attempt the single-vehicle route: re-download the graph if the area is
   * still missing, then ask `/route` again. The failure reason, when there is
   * one, is the backend's own and is rendered verbatim.
   */
  const retrySingle = useCallback(async () => {
    singleRequested.current = false
    setSingleError(null)
    await loadSingle()
  }, [loadSingle])

  const setMode = useCallback(
    (m: Mode) => {
      setModeRaw(m)
      setSelectedVehicle(null)
      if (m === 'single') void loadSingle()
    },
    [loadSingle],
  )

  const reset = useCallback(() => {
    setRuns({})
    setStatus('idle')
    setError('')
    setSelectedVehicle(null)
  }, [])

  const selectVehicle = useCallback((id: number | null) => setSelectedVehicle(id), [])

  const activeRun = useMemo(
    () =>
      runs[solver] ??
      SOLVERS.reduce<OptimizeResponse | null>(
        (found, s) => found ?? runs[s.id] ?? null,
        null,
      ),
    [runs, solver],
  )

  const value = useMemo<DemoValue>(
    () => ({
      view,
      guided,
      mode,
      solver,
      status,
      error,
      runs,
      // Fall back to whatever actually ran, so a solver toggle can never leave
      // the map blank when the other solver is the one with a result.
      activeRun,
      betaSeries: betaSeriesOf(activeRun),
      area,
      areaLoading,
      areaError,
      picking,
      traffic,
      trafficLoading,
      trafficError,
      single,
      singleError,
      selectedVehicle,
      setView,
      setGuided,
      setMode,
      setSolver,
      optimize,
      retrySingle,
      loadAreaByPoint,
      loadAreaByName,
      setPicking,
      refreshTraffic,
      selectVehicle,
      reset,
    }),
    [
      view,
      guided,
      mode,
      solver,
      status,
      error,
      runs,
      activeRun,
      area,
      areaLoading,
      areaError,
      picking,
      traffic,
      trafficLoading,
      trafficError,
      single,
      singleError,
      selectedVehicle,
      setMode,
      optimize,
      retrySingle,
      loadAreaByPoint,
      loadAreaByName,
      refreshTraffic,
      selectVehicle,
      reset,
    ],
  )

  useEffect(() => {
    if (import.meta.env.DEV) {
      ;(window as unknown as { __demo?: DemoValue }).__demo = value
    }
  }, [value])

  return <DemoCtx.Provider value={value}>{children}</DemoCtx.Provider>
}
