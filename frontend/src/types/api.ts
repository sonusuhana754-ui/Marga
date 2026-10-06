/* ===========================================================================
   MARGA API contract.

   This file IS the contract between frontend and backend. The FastAPI response
   models must match these shapes exactly. Any change lands in the PRD (§09)
   first, then here, then in the backend schemas — in that order.

   Endpoints:
     GET  /api/v1/graph
     POST /api/v1/route            single vehicle
     POST /api/v1/optimize         fleet VRP
     GET  /api/v1/stream/:run_id   SSE, one event per sim tick
     POST /api/v1/reoptimize       fires on a threshold crossing or manual incident
     GET  /api/v1/benchmark
=========================================================================== */

/** GeoJSON coordinate order: [longitude, latitude]. */
export type LngLat = [number, number]

export type SolverId =
  | 'dijkstra'
  | 'ortools'
  | 'ga'
  | 'aco'
  | 'pso'
  | 'qpso'
  | 'va_qpso'

export type VehicleClass = 'bike' | 'car' | 'lcv' | 'heavy_truck'

export interface VehicleProfile {
  vehicle_class: VehicleClass
  weight_t: number
  length_m: number
  height_m: number
  width_m: number
}

/* ---- GET /graph ---------------------------------------------------------- */

export interface GraphNode {
  id: number
  lng: number
  lat: number
}

export interface EdgeRestrictions {
  max_weight_t: number | null
  max_height_m: number | null
  no_entry_classes: VehicleClass[]
}

export interface GraphEdge {
  edge_id: string
  u: number
  v: number
  geometry: LngLat[]
  length_m: number
  restrictions: EdgeRestrictions
}

export interface GraphZone {
  zone_id: string
  polygon: LngLat[]
}

export interface GraphResponse {
  city: string
  bbox: [number, number, number, number]
  nodes: GraphNode[]
  edges: GraphEdge[]
  zones: GraphZone[]
  /** Fraction of edges that actually carry OSM restriction tags. Shown honestly. */
  restriction_coverage: number
}

/* ---- POST /route (single vehicle) -------------------------------------- */

export interface RouteRequest {
  city: string
  origin: LngLat
  destination: LngLat
  vehicle_profile: VehicleProfile
  traffic_aware: boolean
}

export interface SingleRoute {
  path: LngLat[]
  distance_m: number
  eta_s: number
  feasible_for_profile: boolean
}

export interface BlockedEdge {
  edge_id: string
  geometry: LngLat[]
  /** e.g. "max_weight_t", "max_height_m", "no_entry" */
  reason: string
  /** the limit value that blocks this vehicle, in the reason's unit */
  limit: number
}

export interface RouteResponse {
  /** shortest for an unrestricted vehicle — the naive baseline */
  unconstrained: SingleRoute
  /** lowest-cost route that is legal for this profile */
  best: SingleRoute
  blocked_edges: BlockedEdge[]
  /** stated honestly — "dijkstra" for single vehicle */
  method: string
}

/* ---- POST /graphs/load (the loaded OSM area) ---------------------------- */

/**
 * A drivable OSM sub-graph the backend has actually downloaded, identified by
 * `graph_key`. Everything geographic in the UI keys off this: which roads the
 * solvers route on, which key `/route` is asked about, and where the map flies.
 */
export interface LoadedArea {
  graph_key: string
  /** Backend's label: a place name, or a point + radius. */
  place: string
  /** Short label for the header. Derived from `place`, never invented. */
  label: string
  /** [lng, lat] centre of the loaded extent, when the backend reported one. */
  center: LngLat | null
  /** [min_lng, min_lat, max_lng, max_lat] of the loaded extent, if known. */
  bounds: [number, number, number, number] | null
  nodes: number
  edges: number
  total_length_km: number
}

/* ---- GET /traffic/snapshot (live speeds) -------------------------------- */

export interface TrafficReading {
  /** Route leg this reading was taken for, as `"a-b"` stop indices. */
  leg?: string
  lng: number
  lat: number
  current_kmh: number
  free_flow_kmh: number
  /** current / free-flow travel time. 1.0 = running free, >1 = delayed. */
  delay_ratio: number
  confidence: number
  road_closure: boolean
}

export interface TrafficSnapshot {
  source: string
  /** UTC ISO-8601 timestamp of the probe batch. */
  observed_at: string
  probes: number
  failed: number
  mean_current_kmh: number
  mean_free_flow_kmh: number
  readings: TrafficReading[]
}

/**
 * The traffic panel's state. `configured: false` means no key is set;
 * `snapshot: null` with `configured: true` means the feed did not answer.
 * Neither case is ever filled in with simulated speeds.
 */
export interface TrafficState {
  configured: boolean
  snapshot: TrafficSnapshot | null
  detail: string | null
}

/* ---- POST /optimize (fleet VRP) --------------------------------------- */

export interface OptimizeRequest {
  city: string
  solver: SolverId
  vehicles: number
  vehicle_profile: VehicleProfile
  capacity: number
  stops: number
  seed: number
}

/** Relative contribution of each cost term to the chosen route. Sums to ~1. */
export interface DecisionWeights {
  traffic: number
  distance: number
  congestion: number
  constraints: number
}

/** A depot or delivery stop as the backend resolved it. */
export interface ScenarioPoint {
  id: number
  lng: number
  lat: number
  demand: number
  is_depot: boolean
}

export interface FleetRoute {
  vehicle_id: number
  /** indices into the scenario's stop list; starts and ends at the depot (0) */
  stop_sequence: number[]
  /**
   * The line this route is drawn and animated along.
   *
   * For `mode:'graph'` runs this is the backend's road-following geometry, so
   * the route follows real streets. Otherwise it is the stop sequence itself —
   * in-code scenarios have no road geometry, and none is invented for them.
   */
  path: LngLat[]
  /** seconds from run start, one per path vertex — drives marker animation */
  timestamps: number[]
  load: number
  distance_m: number
  restrictions_applied: number
  decision_weights: DecisionWeights
  /** [chosen route cost, next-best route cost] */
  cost_vs_next_best: [number, number]
  /**
   * Whether `decision_weights` / `cost_vs_next_best` are real solver output.
   *
   * The OR-Tools backend reports neither a cost-term breakdown nor the runner-up
   * alternative, so we set this to `false` and the panels must say "not reported"
   * instead of drawing invented numbers.
   */
  cost_terms_reported?: boolean
}

export interface ConvergencePoint {
  iteration: number
  best_cost: number
}

export interface ImpactFigures {
  time_saved_s: number
  fuel_saved_l: number
  co2_saved_kg: number
  distance_saved_m: number
  /** true once these are measured, not placeholder */
  measured: boolean
}

export interface OptimizeResponse {
  run_id: string
  solver: SolverId
  total_cost: number
  runtime_ms: number
  vehicles_used: number
  routes: FleetRoute[]
  convergence: ConvergencePoint[]
  impact: ImpactFigures
  /**
   * Depot and stops exactly as the backend resolved them. The map draws these
   * when present; empty means the response carried none, in which case the
   * scene pins are shown instead (and nothing claims they were solved on).
   */
  points: ScenarioPoint[]
  /**
   * Where the numbers in this payload came from. `backend` is the only value:
   * the api layer has no fixture mode, so a failed request surfaces as an
   * error instead of a payload with a different origin.
   */
  source?: 'backend'
  /** Extras the solver chose to report; absent keys mean "not reported". */
  diagnostics: SolverDiagnostics
  /**
   * The OSM area the scenario was built on. Present only for `mode:'graph'`
   * runs; when it is, the depot/stops on the map come from the backend's
   * `points` rather than the scene pins.
   */
  area?: LoadedArea | null
  /**
   * Live traffic readings taken before this solve. Null when no feed is
   * configured or none answered — the panels say so instead of inventing any.
   */
  traffic?: TrafficSnapshot | null
}

/**
 * `solver_diagnostics` from the backend, typed by key. A key that is missing
 * is genuinely not reported by that solver — the panels render "not reported"
 * rather than substituting a default.
 */
export interface SolverDiagnostics {
  iterations?: number
  evaluations?: number
  mean_beta?: number
  /** Measured β, one value per iteration. QPSO variants only. */
  beta_history?: number[]
  /** The [βmin, βmax] the solver was configured with. */
  beta_range?: number[]
  /** False when no traffic feed reaches the solver, so β sits at βmin. */
  volatility_signal?: boolean
  beta_mode?: string
  infeasible_reason?: string
}

/* ---- measured solver diagnostics (rides on POST /optimize) ------------- */

/**
 * One measured β per solver iteration, taken from
 * `solver_diagnostics.beta_history`. Not a time series — the x axis is the
 * iteration the swarm actually evaluated, so the trace stops where the run
 * stopped.
 */
export interface BetaPoint {
  iteration: number
  beta: number
}

/* ---- POST /benchmark ------------------------------------------------ */

/** One solver row. Field names mirror the backend's `BenchmarkResponse`. */
export interface BenchmarkResult {
  solver_id: SolverId
  /** Mean cost across the repetitions. */
  cost: number
  /** Best single-run cost. Reported apart from the mean so neither hides the other. */
  best_cost: number
  /** Cost gap of the mean against the best solver on this scenario, as a percentage. */
  gap_pct: number
  feasible: boolean
  runtime_ms_mean: number
  runtime_ms_min: number
  runtime_ms_max: number
  vehicles_used_min: number
  vehicles_used_max: number
  total_distance_m: number
  total_time_s: number
  /**
   * Best-found cost per iteration from the best run. Empty for solvers that
   * report no per-iteration trace — OR-Tools has none, and the chart says so
   * rather than drawing a curve for it.
   */
  convergence: ConvergencePoint[]
  runs: BenchmarkRun[]
  violations: string[]
}

export interface BenchmarkRun {
  cost: number
  runtime_ms: number
  vehicles_used: number
}

export interface BenchmarkResponse {
  scenario_id: string
  scenario_seed: number
  repeats: number
  /** Lowest feasible cost achieved by any requested solver in this request. */
  best_known: number
  fleet_utilisation: number
  results: BenchmarkResult[]
  /**
   * `backend` = measured by `POST /api/v1/benchmark` during this request. The
   * only value: there is no fixture path, so the view can label every number
   * on screen as measured without a second flag.
   */
  source?: 'backend'
}
