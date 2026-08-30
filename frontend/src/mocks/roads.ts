import type { LngLat } from '@/types/api'
import fleetVa from './data/fleet-va_qpso.json'
import fleetOr from './data/fleet-ortools.json'
import single from './data/single-route.json'

interface RawFleet {
  path: number[][]
}
interface RawSingle {
  unconstrained: { path: number[][] }
  best: { path: number[][] }
}

/**
 * Short road segments derived from the real (OSRM) route geometry we already
 * have. Used for the traffic-congestion overlay and incident targets so those
 * always sit on actual streets, not a synthetic grid.
 */
export interface RoadSegment {
  id: string
  geometry: LngLat[]
  mid: LngLat
}

const paths: LngLat[][] = [
  ...(fleetVa as unknown as RawFleet[]).map((r) => r.path as LngLat[]),
  ...(fleetOr as unknown as RawFleet[]).map((r) => r.path as LngLat[]),
  (single as unknown as RawSingle).unconstrained.path as LngLat[],
  (single as unknown as RawSingle).best.path as LngLat[],
]

const SEG_LEN = 8 // vertices per segment

export const ROAD_SEGMENTS: RoadSegment[] = (() => {
  const segs: RoadSegment[] = []
  let n = 0
  for (const path of paths) {
    for (let i = 0; i + SEG_LEN <= path.length; i += SEG_LEN) {
      const g = path.slice(i, i + SEG_LEN + 1)
      if (g.length < 2) continue
      segs.push({ id: `seg_${n++}`, geometry: g, mid: g[Math.floor(g.length / 2)] })
    }
  }
  return segs
})()

export const ROAD_SEGMENT_GEOM = new Map(ROAD_SEGMENTS.map((s) => [s.id, s.geometry]))
