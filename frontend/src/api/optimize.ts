import type { OptimizeRequest, OptimizeResponse, RouteResponse } from '@/types/api'
import type { BackendOptimizeResponse } from './backendTypes'
import { API_BASE, AREA } from '@/config'
import { fromBackendOptimize, makeRunId, toBackendOptimize } from './adapter'
import points from '@/scene/data/points.json'

/**
 * POST /optimize — fleet CVRP, solved by the backend.
 *
 * No fixture fallback: a rejected promise is the honest outcome when the
 * backend is down, and the dashboard renders an error rather than a fabricated
 * plan.
 */
export async function runOptimize(req: OptimizeRequest): Promise<OptimizeResponse> {
  const res = await fetch(`${API_BASE}/optimize`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(toBackendOptimize(req)),
  })
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`optimize ${res.status}${detail ? ` · ${detail.slice(0, 200)}` : ''}`)
  }
  const body = (await res.json()) as BackendOptimizeResponse
  return fromBackendOptimize(body, req.solver, makeRunId(req.solver))
}

/**
 * POST /route — single vehicle, Dijkstra over the backend's cached OSM graph.
 *
 * The backend only answers this for a graph it has already loaded via
 * `POST /api/v1/graphs/load`, which resolves the place name through OSMnx
 * against live OpenStreetMap. Until that has happened it returns 404 with the
 * reason, and the single-vehicle panel says exactly that instead of drawing a
 * stored route.
 */
export async function runRoute(): Promise<RouteResponse> {
  const res = await fetch(`${API_BASE}/route`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({
      city: AREA.place,
      origin: points.destination,
      destination: points.depot,
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
