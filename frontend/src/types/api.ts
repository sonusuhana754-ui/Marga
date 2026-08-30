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

export interface FleetRoute {
  vehicle_id: number
  /** indices into the scenario's stop list; starts and ends at the depot (0) */
  stop_sequence: number[]
  path: LngLat[]
  /** seconds from run start, one per path vertex — drives marker animation */
  timestamps: number[]
  load: number
  distance_m: number
  restrictions_applied: number
  decision_weights: DecisionWeights
  /** [chosen route cost, next-best route cost] */
  cost_vs_next_best: [number, number]
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
}

/* ---- GET /stream/:run_id (SSE) --------------------------------------- */

export interface VehiclePosition {
  id: number
  lng: number
  lat: number
}

export type CongestionLevel = 'free' | 'moderate' | 'heavy'

export interface EdgeCongestion {
  edge_id: string
  speed_kmh: number
  level: CongestionLevel
}

export interface ZoneVolatility {
  zone_id: string
  sigma_sq: number
  beta: number
}

export type OptStatusState = 'stable' | 'threshold_crossed' | 'reoptimizing'

export interface OptimizationStatus {
  state: OptStatusState
  threshold: number
  cooldown_s: number
  /** zone currently being re-optimized, when state is 'reoptimizing' */
  zone_id?: string
}

export interface StreamTick {
  tick: number
  vehicle_positions: VehiclePosition[]
  /** external traffic only — MARGA's own fleet is never in this signal */
  background_traffic: EdgeCongestion[]
  zone_volatility: ZoneVolatility[]
  optimization_status: OptimizationStatus
}

/* ---- POST /reoptimize ------------------------------------------------ */

export interface ReoptimizeRequest {
  run_id: string
  change: {
    type: 'congestion' | 'closure'
    edge_id: string
  }
}

export interface ReoptimizeResponse {
  triggered_by: 'volatility_threshold' | 'manual_incident'
  affected_zone: string
  affected_vehicles: number[]
  /** only the affected vehicles — same shape as /optimize routes */
  routes: FleetRoute[]
  partial_runtime_ms: number
  full_runtime_ms: number
}

/* ---- GET /benchmark ------------------------------------------------- */

export interface BenchmarkResult {
  solver: SolverId
  cost: number
  gap_pct: number
  runtime_ms: number
  convergence: ConvergencePoint[]
}

export interface BenchmarkResponse {
  instance: string
  best_known: number
  results: BenchmarkResult[]
}
