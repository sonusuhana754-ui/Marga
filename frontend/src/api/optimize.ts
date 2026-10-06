import type { LoadedArea, OptimizeRequest, OptimizeResponse, RouteResponse } from '@/types/api'
import type { BackendOptimizeResponse } from './backendTypes'
import { API_BASE } from '@/config'
import { fromBackendOptimize, makeRunId, toBackendOptimize } from './adapter'

/**
 * POST /optimize — fleet CVRP, solved by the backend.
 *
 * With a loaded OSM area the request is `mode:'graph'`: the backend generates
 * the stops from real junctions and returns road-following geometry. Without
 * one it falls back to `mode:'custom'` over the scene points, which the UI
 * must label as straight-line routing.
 *
 * No fixture fallback: a rejected promise is the honest outcome when the
 * backend is down, and the dashboard renders an error rather than a fabricated
 * plan.
 */
export async function runOptimize(
  req: OptimizeRequest,
  area?: LoadedArea | null,
): Promise<OptimizeResponse> {
  const res = await fetch(`${API_BASE}/optimize`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(toBackendOptimize(req, area)),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`optimize ${res.status}${detail ? ` · ${detail.slice(0, 200)}` : ''}`)
  }
  const body = (await res.json()) as BackendOptimizeResponse
  return fromBackendOptimize(body, req.solver, makeRunId(req.solver))
}

/**
 * Two points inside the loaded extent, spread diagonally so the route has
 * something to cross. Derived from the backend's own bounds — no stored
 * coordinates, so this works for any area the user loads.
 */
function endpointsFor(area: LoadedArea): { origin: [number, number]; destination: [number, number] } {
  const b = area.bounds
  if (!b) {
    const [lng, lat] = area.center ?? [0, 0]
    return { origin: [lng, lat], destination: [lng + 0.004, lat + 0.004] }
  }
  const [minLng, minLat, maxLng, maxLat] = b
  const at = (fx: number, fy: number): [number, number] => [
    minLng + (maxLng - minLng) * fx,
    minLat + (maxLat - minLat) * fy,
  ]
  return { origin: at(0.25, 0.25), destination: at(0.75, 0.75) }
}

/**
 * POST /route — single vehicle, Dijkstra over the backend's cached OSM graph.
 *
 * The graph key, and therefore which roads are considered, comes from the
 * loaded area. Until one is loaded the backend answers 404 with the reason,
 * and the single-vehicle panel says exactly that instead of drawing a stored
 * route.
 */
export async function runRoute(area: LoadedArea): Promise<RouteResponse> {
  const { origin, destination } = endpointsFor(area)
  const res = await fetch(`${API_BASE}/route`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      city: area.graph_key,
      origin,
      destination,
      vehicle_profile: { vehicle_class: 'heavy_truck' },
      traffic_aware: false,
    }),
  })
  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.json()) as { detail?: string }
      detail = body.detail ?? ''
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `route ${res.status}`)
  }
  return (await res.json()) as unknown as RouteResponse
}
