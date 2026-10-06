/* ===========================================================================
   Translation between the FastAPI wire format and the frontend contract.

   One direction, one place. `src/types/api.ts` is what the UI renders;
   `src/api/backendTypes.ts` is what the backend speaks; this file is the only
   place that knows the two differ.

   Everything the backend genuinely reports is carried through untouched:
   `total_cost`, `runtime_ms`, `vehicles_used`, and per-route `stop_sequence`,
   `load`, `distance_m`, `time_s`.

   Two things are *derived*, and both are exact rather than invented:

     path        The custom-scenario builder in `optimize_service.py` lays a
                 complete directed graph over the points we send, with
                 haversine length per edge. A shortest path between two of our
                 points is therefore the straight line between them, so
                 `stop_sequence` plus the coordinates we sent reproduces the
                 backend's own geometry exactly.

     timestamps  Same edges, with `travel_time = length / 50 km/h`
                 (`_DEFAULT_SPEED_MS` in `evaluate.py`). Cumulative leg times
                 are rescaled so the last vertex lands exactly on the
                 `time_s` the backend reported, so the marker animation cannot
                 drift from the measured figure.

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
  LngLat,
  OptimizeRequest,
  OptimizeResponse,
  SolverDiagnostics,
} from '@/types/api'
import type {
  BackendCustomOptimizeRequest,
  BackendOptimizeResponse,
} from './backendTypes'
import { DEPOT, STOPS } from '@/scene/scenario'

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
 * Frontend optimize request -> backend `mode:'custom'` body.
 *
 * Only `stops` of the 10 hand-authored Koramangala points are sent; the rest are
 * held back for larger fleets. `vehicle_profile` and `city` have no counterpart
 * in `CustomScenarioRequest` — the backend models capacity only, and physical
 * restrictions are still a placeholder there — so they are dropped rather than
 * smuggled into a field that does not exist.
 */
export function toBackendOptimize(
  req: OptimizeRequest,
): BackendCustomOptimizeRequest {
  const n = Math.max(1, Math.min(req.stops, STOPS.length))
  const capacity = Math.max(1, Math.floor(req.capacity / Math.max(1, req.vehicles)))
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
    vehicles: Array.from({ length: Math.max(1, req.vehicles) }, (_, i) => ({
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
  const routes: FleetRoute[] = res.routes.map((r) => {
    const path = r.stop_sequence.map(pointAtPosition)

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
