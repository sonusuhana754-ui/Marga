import type { LngLat } from '@/types/api'

const R = 6371000 // earth radius, metres

/** Great-circle distance between two [lng,lat] points, in metres. */
export function haversine(a: LngLat, b: LngLat): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b[1] - a[1])
  const dLng = toRad(b[0] - a[0])
  const lat1 = toRad(a[1])
  const lat2 = toRad(b[1])
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}

/** Total length of a polyline, in metres. */
export function pathLength(path: LngLat[]): number {
  let total = 0
  for (let i = 1; i < path.length; i++) total += haversine(path[i - 1], path[i])
  return total
}

/** Cumulative distance to each vertex of a polyline. */
export function cumulativeLengths(path: LngLat[]): number[] {
  const out = [0]
  for (let i = 1; i < path.length; i++) {
    out.push(out[i - 1] + haversine(path[i - 1], path[i]))
  }
  return out
}

/**
 * Position along a polyline at elapsed time `t` seconds, given per-vertex
 * `timestamps` (seconds from start). Linear interpolation between the bracketing
 * vertices. Clamps to the endpoints outside the timestamp range.
 */
export function positionAtTime(
  path: LngLat[],
  timestamps: number[],
  t: number,
): LngLat {
  if (path.length === 0) return [0, 0]
  if (t <= timestamps[0]) return path[0]
  const last = timestamps.length - 1
  if (t >= timestamps[last]) return path[last]

  let i = 1
  while (i < timestamps.length && timestamps[i] < t) i++
  const t0 = timestamps[i - 1]
  const t1 = timestamps[i]
  const f = t1 === t0 ? 0 : (t - t0) / (t1 - t0)
  const a = path[i - 1]
  const b = path[i]
  return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
}

/** Bearing in degrees (0 = north) from a to b — for orienting a vehicle icon. */
export function bearing(a: LngLat, b: LngLat): number {
  const toRad = (d: number) => (d * Math.PI) / 180
  const toDeg = (r: number) => (r * 180) / Math.PI
  const y = Math.sin(toRad(b[0] - a[0])) * Math.cos(toRad(b[1]))
  const x =
    Math.cos(toRad(a[1])) * Math.sin(toRad(b[1])) -
    Math.sin(toRad(a[1])) * Math.cos(toRad(b[1])) * Math.cos(toRad(b[0] - a[0]))
  return (toDeg(Math.atan2(y, x)) + 360) % 360
}

/** GeoJSON helpers — keep the map components terse. */
export function lineFeature<P extends object>(
  coordinates: LngLat[],
  properties: P,
): GeoJSON.Feature<GeoJSON.LineString, P> {
  return { type: 'Feature', properties, geometry: { type: 'LineString', coordinates } }
}

export function pointFeature<P extends object>(
  coordinate: LngLat,
  properties: P,
): GeoJSON.Feature<GeoJSON.Point, P> {
  return { type: 'Feature', properties, geometry: { type: 'Point', coordinates: coordinate } }
}

export function featureCollection<G extends GeoJSON.Geometry, P>(
  features: GeoJSON.Feature<G, P>[],
): GeoJSON.FeatureCollection<G, P> {
  return { type: 'FeatureCollection', features }
}
