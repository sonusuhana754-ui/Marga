import { describe, expect, it } from 'vitest'
import {
  fromBackendOptimize,
  fromBackendTraffic,
  makeRunId,
  toBackendOptimize,
  type BackendOptimizeRequest,
} from './adapter'
import type { BackendOptimizeResponse, BackendTrafficSnapshot } from './backendTypes'
import type { OptimizeRequest } from '@/types/api'
import { DEPOT, STOPS } from '@/scene/scenario'

/** A frontend request the way DemoProvider builds it. */
function makeRequest(overrides: Partial<OptimizeRequest> = {}): OptimizeRequest {
  return {
    city: 'bengaluru',
    solver: 'va_qpso',
    vehicles: 2,
    vehicle_profile: { vehicle_class: 'heavy_truck', weight_t: 18, length_m: 7, height_m: 4, width_m: 2.5 },
    capacity: 120,
    stops: 14,
    seed: 42,
    ...overrides,
  }
}

const AREA = {
  graph_key: '2.352,48.857,1200m_95d3ed16b923',
  place: 'point 2.3522,48.8566 ±1200m',
  label: 'near 2.3522,48.8566 ±1200m',
  center: [2.3522, 48.8566] as [number, number],
  bounds: [2.3359, 48.8458, 2.3686, 48.8674] as [number, number, number, number],
  nodes: 651,
  edges: 1156,
  total_length_km: 97,
}

const GRAPH = {
  graph_key: AREA.graph_key,
  place: AREA.place,
  center: AREA.center,
  bounds: AREA.bounds,
  nodes: AREA.nodes,
  edges: AREA.edges,
  total_length_km: AREA.total_length_km,
}

const POINTS = [
  { id: 0, lng: 2.35, lat: 48.85, demand: 0, is_depot: true },
  { id: 1, lng: 2.36, lat: 48.86, demand: 5, is_depot: false },
  { id: 2, lng: 2.34, lat: 48.855, demand: 7, is_depot: false },
]

const TRAFFIC: BackendOptimizeResponse['traffic'] = {
  source: 'tomtom',
  observed_at: '2026-10-06T17:20:47+00:00',
  probes: 10,
  failed: 1,
  mean_current_kmh: 17,
  mean_free_flow_kmh: 21.9,
  readings: [
    { leg: '0-1', lng: 2.355, lat: 48.855, current_kmh: 12.5, free_flow_kmh: 20, delay_ratio: 1.6, confidence: 0.9, road_closure: false },
    { lng: 2.36, lat: 48.86, current_kmh: 30, free_flow_kmh: 28 },
  ],
}

/** One backend wire response for a graph run. */
function makeWire(overrides: Partial<BackendOptimizeResponse> = {}): BackendOptimizeResponse {
  return {
    solver: 'va_qpso',
    scenario_id: 'graph_77',
    total_cost: 30_599.1,
    runtime_ms: 214.5,
    vehicles_used: 2,
    feasible: true,
    total_distance_m: 10_724.19,
    total_time_s: 772.14,
    fleet_utilisation: 0.62,
    convergence: [
      { iteration: 1, best_cost: 31_000 },
      { iteration: 2, best_cost: 30_599.1 },
    ],
    solver_diagnostics: {
      iterations: 2,
      mean_beta: 0.4047,
      beta_history: [0.4, 0.4094],
      beta_range: [0.4, 1],
      volatility_signal: true,
      beta_mode: 'adaptive',
    },
    routes: [
      {
        vehicle_id: 0,
        stop_sequence: [0, 1, 0],
        load: 5,
        distance_m: 6_000,
        time_s: 400,
        geometry: [
          [2.35, 48.85],
          [2.355, 48.855],
          [2.36, 48.86],
        ],
      },
      {
        vehicle_id: 1,
        stop_sequence: [0, 2, 0],
        load: 7,
        distance_m: 4_724.19,
        time_s: 372.14,
        geometry: [],
      },
    ],
    points: POINTS,
    graph: GRAPH,
    traffic: TRAFFIC,
    ...overrides,
  }
}

describe('toBackendOptimize', () => {
  it('sends mode=graph against the loaded area, with live traffic enabled', () => {
    const body = toBackendOptimize(makeRequest(), AREA) as BackendOptimizeRequest & {
      mode: 'graph'
    }
    expect(body.mode).toBe('graph')
    expect(body.graph_key).toBe(AREA.graph_key)
    expect(body.solver).toBe('va_qpso')
    expect(body.seed).toBe(42)
    expect(body.vehicles).toBe(2)
    // capacity is split per vehicle so the fleet-wide constraint means anything.
    expect(body.capacity).toBe(60)
    expect(body.traffic).toBe(true)
    expect(body.stops).toBe(14)
  })

  it('clamps stop counts into a range the backend can actually solve', () => {
    const high = toBackendOptimize(makeRequest({ stops: 500 }), AREA)
    const low = toBackendOptimize(makeRequest({ stops: 0 }), AREA)
    expect(high.mode === 'graph' && high.stops).toBe(80)
    expect(low.mode === 'graph' && low.stops).toBe(4)
  })

  it('falls back to the hand-authored scene points only when no area is loaded', () => {
    const body = toBackendOptimize(makeRequest({ stops: 10 }), null)
    expect(body.mode).toBe('custom')
    if (body.mode !== 'custom') throw new Error('expected custom mode')
    expect(body.depot).toEqual({ id: 0, lng: DEPOT[0], lat: DEPOT[1], demand: 0 })
    expect(body.stops).toHaveLength(10)
    expect(body.stops[0]).toEqual({ id: 1, lng: STOPS[0][0], lat: STOPS[0][1], demand: expect.any(Number) })
    expect(body.vehicles).toEqual([
      { id: 0, capacity: 60 },
      { id: 1, capacity: 60 },
    ])
    // Total demand is sized above one vehicle's capacity so a single truck
    // cannot absorb everything — the constraint the solver must respect.
    const total = body.stops.reduce((sum, s) => sum + s.demand, 0)
    expect(total).toBeGreaterThan(60)
    expect(body.time_windows).toBeNull()
  })

  it('never emits fields the backend does not accept', () => {
    const body = toBackendOptimize(makeRequest(), AREA) as unknown as Record<string, unknown>
    expect(body).not.toHaveProperty('city')
    expect(body).not.toHaveProperty('vehicle_profile')
  })
})

describe('fromBackendOptimize', () => {
  it('draws routes from the backend road geometry, not the stop sequence', () => {
    const run = fromBackendOptimize(makeWire(), 'va_qpso', 'r_test')
    const roadRoute = run.routes[0]
    expect(roadRoute.path).toEqual([
      [2.35, 48.85],
      [2.355, 48.855],
      [2.36, 48.86],
    ])
    // A route with no geometry degrades to its stop sequence rather than a
    // fabricated line.
    const straight = run.routes[1]
    expect(straight.path).toHaveLength(3)
    expect(straight.path[0]).toEqual([POINTS[0].lng, POINTS[0].lat])
    // stop_sequence [0, 2, 0] → the point with id 2.
    expect(straight.path[1]).toEqual([POINTS[2].lng, POINTS[2].lat])
  })

  it('carries the backend’s own points, area and traffic through', () => {
    const run = fromBackendOptimize(makeWire(), 'va_qpso', 'r_test')
    expect(run.source).toBe('backend')
    expect(run.total_cost).toBe(30_599.1)
    expect(run.runtime_ms).toBe(214.5)
    expect(run.vehicles_used).toBe(2)
    expect(run.points).toEqual(POINTS)
    expect(run.area).toEqual({
      graph_key: AREA.graph_key,
      place: AREA.place,
      label: 'near point 2.3522,48.8566 ±1200m'.replace('near point', 'near'),
      center: AREA.center,
      bounds: AREA.bounds,
      nodes: AREA.nodes,
      edges: AREA.edges,
      total_length_km: AREA.total_length_km,
    })
    expect(run.traffic?.source).toBe('tomtom')
    expect(run.traffic?.probes).toBe(10)
    expect(run.traffic?.failed).toBe(1)
    expect(run.traffic?.mean_current_kmh).toBe(17)
    expect(run.traffic?.readings).toHaveLength(2)
  })

  it('keeps a null traffic null — no substitute speeds', () => {
    const run = fromBackendOptimize(makeWire({ traffic: null }), 'va_qpso', 'r_test')
    expect(run.traffic).toBeNull()
  })

  it('ends the animation clock exactly on the backend’s reported time_s', () => {
    const run = fromBackendOptimize(makeWire(), 'va_qpso', 'r_test')
    for (const route of run.routes) {
      expect(route.timestamps.at(-1)).toBeCloseTo(
        route.vehicle_id === 0 ? 400 : 372.14,
        2,
      )
      expect(route.timestamps[0]).toBe(0)
      // Monotonic: time only accumulates along the path.
      for (let i = 1; i < route.timestamps.length; i++) {
        expect(route.timestamps[i]).toBeGreaterThanOrEqual(route.timestamps[i - 1])
      }
    }
  })

  it('reports savings as unmeasured until a second solver has run', () => {
    const run = fromBackendOptimize(makeWire(), 'va_qpso', 'r_test')
    expect(run.impact).toEqual({
      time_saved_s: 0,
      fuel_saved_l: 0,
      co2_saved_kg: 0,
      distance_saved_m: 0,
      measured: false,
    })
  })

  it('reads diagnostics at their expected types and drops the rest', () => {
    const run = fromBackendOptimize(makeWire(), 'va_qpso', 'r_test')
    expect(run.diagnostics.mean_beta).toBe(0.4047)
    expect(run.diagnostics.beta_history).toEqual([0.4, 0.4094])
    expect(run.diagnostics.volatility_signal).toBe(true)
    expect(run.diagnostics.beta_range).toEqual([0.4, 1])
    expect(run.diagnostics.beta_mode).toBe('adaptive')

    const bad = fromBackendOptimize(
      makeWire({
        solver_diagnostics: {
          mean_beta: 'high',
          beta_history: ['x'],
        } as unknown as BackendOptimizeResponse['solver_diagnostics'],
      }),
      'qpso',
      'r_bad',
    )
    expect(bad.diagnostics.mean_beta).toBeUndefined()
    expect(bad.diagnostics.beta_history).toBeUndefined()
    expect(bad.diagnostics.volatility_signal).toBeUndefined()
  })

  it('passes an empty convergence through untouched', () => {
    const run = fromBackendOptimize(makeWire({ convergence: [] }), 'ortools', 'r_ort')
    expect(run.convergence).toEqual([])
  })

  it('warns instead of inventing a coordinate for an unknown position', () => {
    const run = fromBackendOptimize(
      makeWire({ routes: [{ vehicle_id: 0, stop_sequence: [0, 9, 0], load: 3, distance_m: 1, time_s: 1, geometry: [] }] }),
      'qpso',
      'r_test',
    )
    // Falls back to the scene pin; the point list has no id 9.
    expect(run.routes[0].path[1]).toEqual(STOPS[8] ?? STOPS[STOPS.length - 1])
  })
})

describe('fromBackendTraffic', () => {
  it('maps readings and defaults missing optional fields honestly', () => {
    const snap = fromBackendTraffic(TRAFFIC as BackendTrafficSnapshot)
    expect(snap.readings[0]).toEqual({
      leg: '0-1',
      lng: 2.355,
      lat: 48.855,
      current_kmh: 12.5,
      free_flow_kmh: 20,
      delay_ratio: 1.6,
      confidence: 0.9,
      road_closure: false,
    })
    // A reading without those fields gets neutral defaults, not zeros that
    // would read as "gridlocked".
    expect(snap.readings[1]).toEqual({
      lng: 2.36,
      lat: 48.86,
      current_kmh: 30,
      free_flow_kmh: 28,
      delay_ratio: 1,
      confidence: 0,
      road_closure: false,
    })
    expect(snap.observed_at).toBe(TRAFFIC!.observed_at)
  })
})

describe('makeRunId', () => {
  it('prefixes the solver so runs are traceable to what produced them', () => {
    expect(makeRunId('va_qpso')).toMatch(/^r_va_qpso_/)
  })
})
