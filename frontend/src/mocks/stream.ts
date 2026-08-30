import type {
  EdgeCongestion,
  StreamTick,
  ZoneVolatility,
} from '@/types/api'
import { BETA_CEILING } from '@/config'
import { mockGraph } from './graph'
import { ROAD_SEGMENTS } from './roads'
import { mulberry32 } from './rng'

/** Seconds of simulated time between stream ticks. */
export const TICK_SECONDS = 10

/**
 * A scripted volatility time-series for the demo. Everything is calm until a
 * traffic surge builds in one zone (~tick 42), volatility crosses the
 * re-optimization threshold (~tick 50), that zone is re-solved, and things
 * settle by ~tick 75. Deterministic.
 *
 * β and σ² are generated as correlated series so the inspector can show them
 * moving together — the real relationship comes from the backend / the paper;
 * the frontend only visualises whatever it receives.
 */
export function mockStream(durationSeconds: number): StreamTick[] {
  const zones = mockGraph.zones
  const rnd = mulberry32(4471)
  const nTicks = Math.max(2, Math.ceil(durationSeconds / TICK_SECONDS) + 1)

  // hot zone = the one containing the most real road-segment midpoints, so the
  // surge always lands where the fleet actually drives
  const hotZoneObj =
    zones
      .map((z) => ({
        z,
        count: ROAD_SEGMENTS.filter((s) => pointInPoly(s.mid, z.polygon)).length,
      }))
      .sort((a, b) => b.count - a.count)[0]?.z ?? zones[0]
  const hotZone = hotZoneObj.zone_id
  const hotCentroid = centroid(hotZoneObj.polygon)

  const congestingEdges = [...ROAD_SEGMENTS]
    .filter((s) => pointInPoly(s.mid, hotZoneObj.polygon))
    .sort((a, b) => dist(a.mid, hotCentroid) - dist(b.mid, hotCentroid))
    .slice(0, 6)

  const SURGE_START = 42
  const SURGE_PEAK = 52
  const SURGE_END = 76

  const surge = (t: number) => {
    if (t < SURGE_START || t > SURGE_END) return 0
    const half = SURGE_PEAK - SURGE_START
    const x = t <= SURGE_PEAK ? (t - SURGE_START) / half : (SURGE_END - t) / (SURGE_END - SURGE_PEAK)
    return Math.max(0, Math.min(1, x))
  }

  const ticks: StreamTick[] = []
  for (let i = 0; i < nTicks; i++) {
    const s = surge(i)

    const zone_volatility: ZoneVolatility[] = zones.map((z) => {
      const noise = 0.04 + rnd() * 0.08
      const isHot = z.zone_id === hotZone
      const sigma_sq = isHot ? noise + s * 0.82 : noise + s * 0.12 * rnd()
      // β tracks volatility: calm ≈ 1.0, volatile pushes toward the ceiling
      const beta = 1.0 + Math.min(sigma_sq, 1) * (BETA_CEILING - 1.0) * (isHot ? 0.9 : 0.4)
      return {
        zone_id: z.zone_id,
        sigma_sq: round(sigma_sq),
        beta: round(beta),
      }
    })

    const hotSigma = zone_volatility.find((z) => z.zone_id === hotZone)?.sigma_sq ?? 0
    const background_traffic: EdgeCongestion[] = congestingEdges.map((e, ei) => {
      const level: EdgeCongestion['level'] =
        s > 0.55 && ei < 4 ? 'heavy' : s > 0.2 ? 'moderate' : 'free'
      return {
        edge_id: e.id,
        speed_kmh: level === 'heavy' ? 8 + rnd() * 6 : level === 'moderate' ? 18 + rnd() * 8 : 34 + rnd() * 10,
        level,
      }
    })

    let state: StreamTick['optimization_status']['state'] = 'stable'
    let zone_id: string | undefined
    if (i >= 51 && i <= 58) {
      state = 'reoptimizing'
      zone_id = hotZone
    } else if (hotSigma >= 0.6) {
      state = 'threshold_crossed'
      zone_id = hotZone
    }

    ticks.push({
      tick: i,
      vehicle_positions: [],
      background_traffic,
      zone_volatility,
      optimization_status: { state, threshold: 0.6, cooldown_s: 30, zone_id },
    })
  }

  return ticks
}

export function tickAt(series: StreamTick[], simSeconds: number): StreamTick | null {
  if (series.length === 0) return null
  const i = Math.max(0, Math.min(series.length - 1, Math.floor(simSeconds / TICK_SECONDS)))
  return series[i]
}

const round = (n: number) => Number(n.toFixed(3))
const dist = (a: [number, number], b: [number, number]) => Math.hypot(a[0] - b[0], a[1] - b[1])

/** point-in-rectangle (zones are axis-aligned rectangles) */
function pointInPoly(p: [number, number], poly: [number, number][]): boolean {
  const xs = poly.map((c) => c[0])
  const ys = poly.map((c) => c[1])
  return (
    p[0] >= Math.min(...xs) &&
    p[0] <= Math.max(...xs) &&
    p[1] >= Math.min(...ys) &&
    p[1] <= Math.max(...ys)
  )
}
function centroid(poly: [number, number][]): [number, number] {
  let x = 0
  let y = 0
  for (const [lng, lat] of poly) {
    x += lng
    y += lat
  }
  return [x / poly.length, y / poly.length]
}
