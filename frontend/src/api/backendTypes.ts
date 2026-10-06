/* ===========================================================================
   MARGA backend wire format — what FastAPI actually speaks.

   This is NOT the frontend contract. `src/types/api.ts` is the contract the UI
   renders; this file mirrors `backend/app/schemas/*.py` so `src/api/adapter.ts`
   can translate between the two in one direction, in one place.

   The two shapes disagree on purpose-agnostic grounds:

     request   frontend  { city, solver, vehicles, vehicle_profile, capacity,
                          stops, seed }
               backend   a tagged union discriminated on `mode`:
                          { mode:'named', scenario_id, solver, seed }
                        | { mode:'custom', solver, seed, depot, stops[],
                            vehicles[], time_windows? }

     response  frontend  { run_id, solver, total_cost, runtime_ms, vehicles_used,
                          routes[{ ..., path, timestamps, restrictions_applied,
                                   decision_weights, cost_vs_next_best }],
                          convergence[], impact{} }
               backend   { solver, scenario_id, total_cost, runtime_ms,
                          vehicles_used, feasible, total_distance_m, total_time_s,
                          fleet_utilisation, convergence[], solver_diagnostics{},
                          routes[{ vehicle_id, stop_sequence, load,
                                   distance_m, time_s }] }

   Keep this file in step with the backend. If you change a schema here, change
   `backend/app/schemas/` in the same commit and say so in the PR body.
   =========================================================================== */

import type { SolverId } from '@/types/api'

/* ---- POST /optimize (mode='custom') -------------------------------------- */

/**
 * `CustomStop.id` doubles as the index into the scenario's stop list on the
 * backend — see the `pid_to_gnode`/`scenario_stops` construction in
 * `backend/app/services/optimize_service.py`. That service mixes node positions
 * and stop ids (the demand callback indexes by `stop.id`, evaluation indexes the
 * list by position), so the two only agree when `id == position`. The adapter
 * therefore always numbers the depot 0 and the stops 1..n.
 */
export interface BackendStop {
  id: number
  lng: number
  lat: number
  demand: number
}

export interface BackendVehicle {
  id: number
  capacity: number
}

export interface BackendTimeWindow {
  stop_id: number
  earliest: number
  latest: number
}

export interface BackendCustomOptimizeRequest {
  mode: 'custom'
  solver: SolverId
  seed: number | null
  depot: BackendStop
  stops: BackendStop[]
  vehicles: BackendVehicle[]
  time_windows?: BackendTimeWindow[] | null
}

/* ---- POST /optimize response -------------------------------------------- */

export interface BackendOptimizeRoute {
  vehicle_id: number
  /** node positions, always starting and ending at 0 (the depot) */
  stop_sequence: number[]
  load: number
  distance_m: number
  time_s: number
}

export interface BackendConvergencePoint {
  iteration: number
  best_cost: number
}

export interface BackendOptimizeResponse {
  solver: string
  scenario_id: string
  total_cost: number
  runtime_ms: number
  vehicles_used: number
  /** False when no route set the fleet may legally run was found. */
  feasible: boolean
  total_distance_m: number
  total_time_s: number
  fleet_utilisation: number
  /**
   * Best-found cost per iteration. Reported by the QPSO variants; always empty
   * for OR-Tools, which has no per-iteration hook. That asymmetry is real
   * information, so an empty array is passed through rather than filled in.
   */
  convergence: BackendConvergencePoint[]
  /**
   * Per-solver extras, dropped when absent: `iterations`, `evaluations`,
   * `mean_beta`, `beta_history` (measured β, one value per iteration),
   * `beta_range` ([βmin, βmax] the solver was configured with),
   * `volatility_signal` (false when no traffic feed reaches the solver),
   * `beta_mode`, `infeasible_reason`.
   */
  solver_diagnostics: Record<string, number | string | boolean | number[]>
  routes: BackendOptimizeRoute[]
}

/* ---- POST /route --------------------------------------------------------- */

export interface BackendRouteResponse {
  unconstrained: {
    path: [number, number][]
    distance_m: number
    eta_s: number
    feasible_for_profile: boolean
  }
  best: {
    path: [number, number][]
    distance_m: number
    eta_s: number
    feasible_for_profile: boolean
  }
  blocked_edges: {
    edge_id: string
    geometry: [number, number][]
    reason: string
    limit: number
  }[]
  method: string
}