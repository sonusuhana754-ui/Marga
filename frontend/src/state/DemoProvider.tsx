import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import type { BetaPoint, OptimizeResponse, RouteResponse, SolverId } from '@/types/api'
import { runOptimize, runRoute } from '@/api/optimize'
import { AREA, API_BASE, ASSUMPTIONS, DEFAULT_PROFILE, DEFAULT_SOLVER, SOLVERS } from '@/config'
import { DemoCtx } from './demoStore'
import type { DemoValue, Mode, View } from './demoStore'

/** Measured β per iteration, taken from the solver's own diagnostics. */
function betaSeriesOf(run: OptimizeResponse | null): BetaPoint[] | null {
  const history = run?.diagnostics.beta_history
  if (!history || history.length === 0) return null
  return history.map((beta, iteration) => ({ iteration, beta }))
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

  const optimize = useCallback(async () => {
    setStatus('optimizing')
    setError('')
    setSelectedVehicle(null)
    const base = {
      city: AREA.id,
      vehicles: 2,
      vehicle_profile: DEFAULT_PROFILE,
      capacity: 100,
      stops: 10,
      seed: 42,
    }
    const wanted = SOLVERS.map((s) => s.id)
    const settled = await Promise.allSettled(
      wanted.map((id) => runOptimize({ ...base, solver: id })),
    )

    const next: Partial<Record<SolverId, OptimizeResponse>> = {}
    const failures: string[] = []
    settled.forEach((result, i) => {
      if (result.status === 'fulfilled') next[wanted[i]] = result.value
      else {
        const reason = result.reason instanceof Error ? result.reason.message : String(result.reason)
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
        (baseline.routes.reduce((s, r) => s + r.distance_m, 0) -
          ours.routes.reduce((s, r) => s + r.distance_m, 0)),
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
  }, [])

  /** Single-vehicle route, fetched from the backend. Failures stay visible. */
  const singleRequested = useRef(false)
  const loadSingle = useCallback(async () => {
    if (singleRequested.current) return
    singleRequested.current = true
    try {
      setSingle(await runRoute())
      setSingleError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      setSingleError(message)
      console.warn('[route] unavailable:', message)
    }
  }, [])

  /**
   * Ask the backend to cache the OSM graph for the demo place, then retry the
   * route. The download is a multi-second OSMnx fetch and can fail on its own,
   * so its failure is reported through the same `singleError` string.
   */
  const retrySingle = useCallback(async () => {
    singleRequested.current = true
    setSingleError(null)
    try {
      const res = await fetch(`${API_BASE}/graphs/load`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ place: AREA.place, force_reload: false }),
      })
      if (!res.ok) throw new Error(`graphs/load ${res.status}`)
      setSingle(await runRoute())
      setSingleError(null)
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      singleRequested.current = false
      setSingleError(message)
      console.warn('[graphs/load] failed:', message)
    }
  }, [])

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
      single,
      singleError,
      selectedVehicle,
      setView,
      setGuided,
      setMode,
      setSolver,
      optimize,
      retrySingle,
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
      single,
      singleError,
      selectedVehicle,
      setMode,
      optimize,
      retrySingle,
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
