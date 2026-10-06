/* ===========================================================================
   Translation between the FastAPI wire format and the frontend contract.

   One direction, one place. `src/types/api.ts` is what the UI renders;
   `src/api/backendTypes.ts` is what the backend speaks; this file is the only
   place that knows the two differ.

   Everything the backend genuinely reports is carried through untouched:
   `total_cost`, `runtime_ms`, `vehicles_used`, and per-route `stop_sequence`,
   `load`, `distance_m`, `time_s`, plus — for `mode:'graph'` runs — the
   backend's own depot/stop coordinates and road-following `geometry`.

   Two things are *derived*, and both are exact rather than invented:

     path        For a graph run the backend's road geometry is used verbatim,
                 so routes follow real streets. Otherwise the custom-scenario
                 builder in `optimize_service.py` lays a complete directed
                 graph over the points we send, with haversine length per edge:
                 a shortest path between two of our points is the straight line
                 between them, so `stop_sequence` plus the reported points
                 reproduces the backend's own geometry exactly.

     timestamps  Cumulative travel time along that path, rescaled so the last
                 vertex lands exactly on the `time_s` the backend reported, so
                 the marker animation cannot drift from the measured figure.

   One thing is *not* available, and is reported as such rather than faked:
   no solver exposes a per-route cost-term breakdown or a runner-up alternative,
   so `cost_terms_reported: false` makes WhyRoute say so.

   `convergence` is the one field that is now genuinely measured end to end: the
   QPSO variants (`qpso`, `va_qpso`) report best-found cost per iteration, and
   OR-Tools reports none because its search has no per-iteration hook to expose.
   The empty list is the honest value for that case.
   =========================================================================== */

import type {
  DecisionWeights,
  FleetRoute,
  LoadedArea,
  LngLat,
  OptimizeRequest,
  OptimizeResponse,
  SolverDiagnostics,
  TrafficSnapshot,
} from '@/types/api'
import type {
  BackendCustomOptimizeRequest,
  BackendGraphOptimizeRequest,
  BackendOptimizeResponse,
  BackendTrafficSnapshot,
} from './backendTypes'
import { DEPOT, STOPS } from '@/scene/scenario'

/** Either wire shape; `mode` tells them apart. */
export type BackendOptimizeRequest = BackendCustomOptimizeRequest | BackendGraphOptimizeRequest

/**
 * The backend's fixed default speed, `_DEFAULT_SPEED_MS` in
 * `backend/app/algorithms/evaluate.py`. Travel time per leg is derived from it,
 * so the animation clock and the reported `time_s` agree.
 */
const BACKEND_SPEED_MPS = (50.0 * 1000.0) / 3600.0

/** Depot is position 0; stop at position p>0 is STOPS[p-1]. Mirrors backend indexing. */
function pointAtPosition(position: number): LngLat {
  return position === 0 ? DEPOT : STOPS[position - 1] ?? DEPOT
}

/**
 * Position → coordinate resolver for one response.
 *
 * The backend now reports every depot/stop it actually solved on, so those
 * values win: the map is drawn from what the solver saw, not from the scene
 * pins. The pins remain only as the fallback for a response that carries no
 * points, which today means nothing at all.
 */
function resolverFor(res: BackendOptimizeResponse): (position: number) => LngLat {
  const points = res.points ?? []
  if (points.length === 0) return pointAtPosition
  const byId = new Map(points.map((p) => [p.id, p] as const))
  return (position) => {
    const point = byId.get(position) ?? points[position]
    if (!point) {
      console.warn(`[adapter] no backend point for position ${position}`)
      return pointAtPosition(position)
    }
    return [point.lng, point.lat]
  }
}

/** Deterministic 32-bit LCG so a given seed always yields the same demands. */
function lcg(seed: number): () => number {
  let s = (seed >>> 0) || 1
  return () => {
    s = (Math.imul(s, 1664525) + 1013904223) >>> 0
    return s / 0x1_0000_0000
  }
}

/**
 * Per-stop demand, sized so the fleet's capacity constraint actually binds:
 * total demand lands near 1.5x a single vehicle's capacity, which is what forces
 * the solver to use more than one truck instead of collapsing onto one.
 */
function buildDemands(n: number, capacity: number, seed: number): number[] {
  if (n === 0) return []
  const base = Math.max(1, Math.floor((capacity * 1.5) / n))
  const rnd = lcg(seed)
  return Array.from({ length: n }, () => base + Math.floor(rnd() * 3))
}

/**
 * Frontend optimize request → backend body.
 *
 * Two shapes, chosen honestly:
 *
 *   `mode:'graph'`  when an OSM area is loaded — the backend generates the
 *                   depot and stops from real junctions and returns real road
 *                   geometry. This is the normal path.
 *
 *   `mode:'custom'` when no graph is loaded — the hand-authored scene points
 *                   are sent and the backend solves a complete graph over them
 *                   with haversine distances (straight lines, no roads). The
 *                   caption has to say so; nothing here pretends otherwise.
 *
 * `vehicle_profile` and `city` have no counterpart in either backend request —
 * the backend models capacity only, and physical restrictions are still a
 * placeholder there — so they are dropped rather than smuggled into a field
 * that does not exist.
 */
export function toBackendOptimize(
  req: OptimizeRequest,
  area?: LoadedArea | null,
): BackendOptimizeRequest {
  const vehicles = Math.max(1, req.vehicles)

  if (area) {
    const capacity = Math.max(1, Math.floor(req.capacity / vehicles))
    return {
      mode: 'graph',
      solver: req.solver,
      seed: req.seed,
      graph_key: area.graph_key,
      stops: Math.max(4, Math.min(req.stops, 80)),
      vehicles,
      capacity,
      // Probing live traffic is what puts observations in the volatility
      // window; the backend reports `traffic: null` if no feed answers.
      traffic: true,
    }
  }

  const n = Math.max(1, Math.min(req.stops, STOPS.length))
  const capacity = Math.max(1, Math.floor(req.capacity / vehicles))
  const demands = buildDemands(n, capacity, req.seed)

  return {
    mode: 'custom',
    solver: req.solver,
    seed: req.seed,
    depot: { id: 0, lng: DEPOT[0], lat: DEPOT[1], demand: 0 },
    stops: STOPS.slice(0, n).map(([lng, lat], i) => ({
      id: i + 1,
      lng,
      lat,
      demand: demands[i],
    })),
    vehicles: Array.from({ length: vehicles }, (_, i) => ({
      id: i,
      capacity,
    })),
    time_windows: null,
  }
}

/** Backend response -> frontend contract. */
export function fromBackendOptimize(
  res: BackendOptimizeResponse,
  solver: OptimizeRequest['solver'],
  runId: string,
): OptimizeResponse {
  const resolvePoint = resolverFor(res)

  const routes: FleetRoute[] = res.routes.map((r) => {
    // Graph runs draw and animate along the road polyline the backend
    // computed; anything else has only the stop sequence to work with.
    const hasGeometry = (r.geometry?.length ?? 0) >= 2
    const path: LngLat[] = hasGeometry
      ? r.geometry.map(([lng, lat]) => [lng, lat] as LngLat)
      : r.stop_sequence.map(resolvePoint)

    // Cumulative leg time from the same edges the backend built, rescaled so the
    // final vertex equals the time_s it actually reported.
    const raw: number[] = [0]
    for (let i = 1; i < path.length; i++) {
      const dLat = ((path[i][1] - path[i - 1][1]) * Math.PI) / 180
      const dLng = ((path[i][0] - path[i - 1][0]) * Math.PI) / 180
      const h =
        Math.sin(dLat / 2) ** 2 +
        Math.cos((path[i - 1][1] * Math.PI) / 180) *
          Math.cos((path[i][1] * Math.PI) / 180) *
          Math.sin(dLng / 2) ** 2
      const metres = 2 * 6_371_000 * Math.asin(Math.sqrt(h))
      raw.push(raw[i - 1] + metres / BACKEND_SPEED_MPS)
    }
    const rawTotal = raw[raw.length - 1]
    const scale = rawTotal > 0 ? r.time_s / rawTotal : 1
    const timestamps = raw.map((t) => Math.round(t * scale * 1000) / 1000)

    // The backend objective is `distance + time * 50 km/h`, i.e. entirely
    // distance-equivalent. Traffic, congestion and vehicle constraints do not
    // enter the cost at all, so they are weighted zero rather than faked.
    const decisionWeights: DecisionWeights = {
      traffic: 0,
      distance: 1,
      congestion: 0,
      constraints: 0,
    }
    const routeCost = r.distance_m + r.time_s * BACKEND_SPEED_MPS

    return {
      vehicle_id: r.vehicle_id,
      stop_sequence: r.stop_sequence,
      path,
      timestamps,
      load: r.load,
      distance_m: r.distance_m,
      // No restriction-aware routing exists on the backend yet, so nothing is
      // genuinely "applied" — zero keeps the panel honest rather than implying
      // the solver steered around weight/height limits.
      restrictions_applied: 0,
      decision_weights: decisionWeights,
      // The runner-up alternative is not exposed by the backend; see the note at
      // the top of this file and `cost_terms_reported` below.
      cost_vs_next_best: [routeCost, routeCost],
      cost_terms_reported: false,
    }
  })

  return {
    run_id: runId,
    solver,
    total_cost: res.total_cost,
    runtime_ms: res.runtime_ms,
    vehicles_used: res.vehicles_used,
    routes,
    // Carried through from the backend. The QPSO variants report a real
    // per-iteration best-so-far trace; OR-Tools has no such hook and sends an
    // empty list, which is passed on as-is rather than replaced with a
    // plausible-looking decay curve.
    convergence: res.convergence ?? [],
    // Savings are a *difference* between two solvers, so they are measured in
    // DemoProvider once more than one solver has actually run. Nothing is
    // pre-filled here.
    impact: {
      time_saved_s: 0,
      fuel_saved_l: 0,
      co2_saved_kg: 0,
      distance_saved_m: 0,
      measured: false,
    },
    source: 'backend',
    diagnostics: readDiagnostics(res.solver_diagnostics),
    points: (res.points ?? []).map((p) => ({
      id: p.id,
      lng: p.lng,
      lat: p.lat,
      demand: p.demand,
      is_depot: p.is_depot,
    })),
    area: res.graph
      ? {
          graph_key: res.graph.graph_key,
          place: res.graph.place,
          label: res.graph.place.replace(/^point /, 'near '),
          center: res.graph.center,
          bounds: res.graph.bounds,
          nodes: res.graph.nodes,
          edges: res.graph.edges,
          total_length_km: res.graph.total_length_km,
        }
      : null,
    // A null here is a real null: no feed configured, or none answered. The
    // panels render that state instead of substituting plausible speeds.
    traffic: res.traffic ? fromBackendTraffic(res.traffic) : null,
  }
}

/** One wire reading batch → the contract's `TrafficSnapshot`. */
export function fromBackendTraffic(raw: BackendTrafficSnapshot): TrafficSnapshot {
  return {
    source: raw.source,
    observed_at: raw.observed_at,
    probes: raw.probes,
    failed: raw.failed,
    mean_current_kmh: raw.mean_current_kmh,
    mean_free_flow_kmh: raw.mean_free_flow_kmh,
    readings: raw.readings.map((reading) => {
      const fields = reading as Record<string, unknown>
      const field = (key: string, fallback = 0) =>
        typeof fields[key] === 'number' ? (fields[key] as number) : fallback
      return {
        ...(typeof fields.leg === 'string' ? { leg: fields.leg } : {}),
        lng: field('lng'),
        lat: field('lat'),
        current_kmh: field('current_kmh'),
        free_flow_kmh: field('free_flow_kmh'),
        delay_ratio: field('delay_ratio', 1),
        confidence: field('confidence'),
        road_closure: fields.road_closure === true,
      }
    }),
  }
}

/**
 * `solver_diagnostics` is an open bag on the wire. Only the keys the UI
 * understands are surfaced, each kept only at its expected type, so an
 * unexpected payload cannot masquerade as a number.
 */
function readDiagnostics(raw: BackendOptimizeResponse['solver_diagnostics']): SolverDiagnostics {
  const d = raw ?? {}
  const at = (k: string) => d[k]
  const num = (k: string) => {
    const v = at(k)
    return typeof v === 'number' ? v : undefined
  }
  const bool = (k: string) => {
    const v = at(k)
    return typeof v === 'boolean' ? v : undefined
  }
  const str = (k: string) => {
    const v = at(k)
    return typeof v === 'string' ? v : undefined
  }
  const nums = (k: string) => {
    const v = at(k)
    return Array.isArray(v) && v.every((x) => typeof x === 'number') ? (v as number[]) : undefined
  }
  return {
    iterations: num('iterations'),
    evaluations: num('evaluations'),
    mean_beta: num('mean_beta'),
    beta_history: nums('beta_history'),
    beta_range: nums('beta_range'),
    volatility_signal: bool('volatility_signal'),
    beta_mode: str('beta_mode'),
    infeasible_reason: str('infeasible_reason'),
  }
}

/** Fresh run id for a live run. The backend does not mint one. */
export function makeRunId(solver: string): string {
  return `r_${solver}_${Date.now().toString(36)}`
}
