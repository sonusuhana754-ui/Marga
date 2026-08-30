import type { LngLat } from '@/types/api'

export type BBox = [[number, number], [number, number]]

/** Bounding box [[w,s],[e,n]] enclosing every point of every path. */
export function boundsOf(paths: LngLat[][]): BBox | null {
  let w = Infinity
  let s = Infinity
  let e = -Infinity
  let n = -Infinity
  for (const path of paths) {
    for (const [lng, lat] of path) {
      if (lng < w) w = lng
      if (lng > e) e = lng
      if (lat < s) s = lat
      if (lat > n) n = lat
    }
  }
  if (!Number.isFinite(w)) return null
  return [
    [w, s],
    [e, n],
  ]
}

/** Left rail + bottom strip clearance for fitBounds padding. */
export const FIT_PADDING = { top: 96, right: 64, bottom: 148, left: 320 }
