import type {
  GraphEdge,
  GraphNode,
  GraphResponse,
  GraphZone,
  LngLat,
} from '@/types/api'
import { AREA } from '@/config'
import { haversine } from '@/lib/geo'
import { mulberry32 } from './rng'

/**
 * A synthetic street-ish graph over the AREA bbox. It is NOT drawn as roads
 * (the base map already has those) — it exists so zones, blocked edges and
 * incident targets have real geometry to reference. Deterministic per seed.
 */
function buildGraph(seed = 26137): GraphResponse {
  const rnd = mulberry32(seed)
  const [w, s, e, n] = AREA.bbox
  const cols = 13
  const rows = 10
  const dx = (e - w) / (cols - 1)
  const dy = (n - s) / (rows - 1)

  const nodes: GraphNode[] = []
  const idAt = (c: number, r: number) => r * cols + c
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      const jx = (rnd() - 0.5) * dx * 0.55
      const jy = (rnd() - 0.5) * dy * 0.55
      nodes.push({ id: idAt(c, r), lng: w + c * dx + jx, lat: s + r * dy + jy })
    }
  }

  const coord = (id: number): LngLat => [nodes[id].lng, nodes[id].lat]
  const edges: GraphEdge[] = []
  let restricted = 0
  const addEdge = (u: number, v: number, key: string) => {
    if (rnd() < 0.14) return // dropped street
    const geometry: LngLat[] = [coord(u), coord(v)]
    const length_m = haversine(geometry[0], geometry[1])
    const roll = rnd()
    const restrictions =
      roll < 0.05
        ? { max_weight_t: 7.5, max_height_m: null, no_entry_classes: [] as never[] }
        : roll < 0.09
          ? { max_weight_t: null, max_height_m: 4.5, no_entry_classes: [] as never[] }
          : { max_weight_t: null, max_height_m: null, no_entry_classes: [] as never[] }
    if (restrictions.max_weight_t || restrictions.max_height_m) restricted++
    edges.push({ edge_id: `e_${key}`, u, v, geometry, length_m, restrictions })
  }
  for (let r = 0; r < rows; r++) {
    for (let c = 0; c < cols; c++) {
      if (c < cols - 1) addEdge(idAt(c, r), idAt(c + 1, r), `${c}_${r}_h`)
      if (r < rows - 1) addEdge(idAt(c, r), idAt(c, r + 1), `${c}_${r}_v`)
    }
  }

  // Zones in a 4×3 grid over the bbox.
  const zones: GraphZone[] = []
  const zc = 4
  const zr = 3
  for (let r = 0; r < zr; r++) {
    for (let c = 0; c < zc; c++) {
      const x0 = w + (c / zc) * (e - w)
      const x1 = w + ((c + 1) / zc) * (e - w)
      const y0 = s + (r / zr) * (n - s)
      const y1 = s + ((r + 1) / zr) * (n - s)
      zones.push({
        zone_id: `z_${r * zc + c}`,
        polygon: [
          [x0, y0],
          [x1, y0],
          [x1, y1],
          [x0, y1],
          [x0, y0],
        ],
      })
    }
  }

  return {
    city: AREA.id,
    bbox: AREA.bbox,
    nodes,
    edges,
    zones,
    restriction_coverage: Number((restricted / edges.length).toFixed(3)),
  }
}

export const mockGraph: GraphResponse = buildGraph()

/** Which zone a point falls in — used to label incidents and volatility. */
export function zoneAt(point: LngLat): string {
  const [w, s, e, n] = AREA.bbox
  const c = Math.min(3, Math.max(0, Math.floor(((point[0] - w) / (e - w)) * 4)))
  const r = Math.min(2, Math.max(0, Math.floor(((point[1] - s) / (n - s)) * 3)))
  return `z_${r * 4 + c}`
}
