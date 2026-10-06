/**
 * Graph loading and live traffic.
 *
 * `POST /graphs/download` downloads a real OSM sub-graph (place name or
 * arbitrary [lng, lat] point) and returns its key, extent, and size.
 * `GET /traffic/snapshot` reads live speeds over a loaded graph.
 *
 * Nothing here has a fallback: a failed download surfaces as a thrown error
 * with the backend's reason, and a missing traffic key comes back as
 * `configured: false`, which the UI states rather than papering over.
 */

import type { LoadedArea, LngLat, TrafficState } from '@/types/api'
import type {
  BackendGraphLoadResponse,
  BackendTrafficSnapshotResponse,
} from './backendTypes'
import { API_BASE } from '@/config'
import { fromBackendTraffic } from './adapter'

/** Wire metadata → the frontend's `LoadedArea`, plus a label for the header. */
function toLoadedArea(res: BackendGraphLoadResponse): LoadedArea {
  const m = res.metadata
  return {
    graph_key: res.graph_key,
    place: m.place,
    // "point 77.5946,12.9716 ±800m" reads badly in a header; "near …" does not.
    label: m.place.replace(/^point /, 'near '),
    center: m.center ?? null,
    bounds: m.bounds ?? null,
    nodes: m.nodes,
    edges: m.edges,
    total_length_km: m.total_length_km,
  }
}

async function post(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`${path} ${res.status}${text ? ` · ${text.slice(0, 240)}` : ''}`)
  }
  return res.json()
}

/** Load the drivable network within `dist_m` of an arbitrary point. */
export async function loadAreaByCenter(
  center: LngLat,
  distM = 1200,
): Promise<LoadedArea> {
  const json = (await post('/graphs/load', {
    center,
    dist_m: distM,
    force_reload: false,
  })) as BackendGraphLoadResponse
  return toLoadedArea(json)
}

/** Load the drivable network for a named place ("Indiranagar, Bengaluru"). */
export async function loadAreaByPlace(place: string): Promise<LoadedArea> {
  const json = (await post('/graphs/load', {
    place,
    force_reload: false,
  })) as BackendGraphLoadResponse
  return toLoadedArea(json)
}

/**
 * Read live speeds over a loaded graph. Never throws for "no feed": an
 * unconfigured backend answers `configured: false`, which is a state the UI
 * renders, not an error.
 */
export async function fetchTraffic(graphKey: string): Promise<TrafficState> {
  const res = await fetch(
    `${API_BASE}/traffic/snapshot?graph_key=${encodeURIComponent(graphKey)}&points=8`,
  )
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`traffic/snapshot ${res.status}${text ? ` · ${text.slice(0, 200)}` : ''}`)
  }
  const body = (await res.json()) as BackendTrafficSnapshotResponse
  return {
    configured: body.configured,
    snapshot: body.snapshot ? fromBackendTraffic(body.snapshot) : null,
    detail: body.detail,
  }
}
