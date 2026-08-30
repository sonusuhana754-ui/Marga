import { useMemo } from 'react'
import { TriangleAlert } from 'lucide-react'
import type { BlockedEdge, LngLat } from '@/types/api'
import { featureCollection, lineFeature } from '@/lib/geo'
import { useSourceLayers } from './useSourceLayers'
import type { LayerDef } from './useSourceLayers'
import { MapMarker } from './MapMarker'

const LAYERS: LayerDef[] = [
  {
    id: 'blocked-casing',
    type: 'line',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#090e10', 'line-width': 9 },
  },
  {
    id: 'blocked-line',
    type: 'line',
    layout: { 'line-cap': 'butt', 'line-join': 'round' },
    paint: {
      'line-color': '#ee6b4d',
      'line-width': 5,
      'line-dasharray': [1.4, 1.2],
    },
  },
]

const REASON_LABEL: Record<string, (limit: number) => string> = {
  max_height_m: (l) => `${l} m clearance`,
  max_weight_t: (l) => `${l} t limit`,
  no_entry: () => 'no entry',
}

function midpoint(geom: LngLat[]): LngLat {
  const i = Math.max(0, Math.floor(geom.length / 2) - 1)
  const a = geom[i]
  const b = geom[i + 1] ?? geom[i]
  return [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]
}

export function BlockedEdges({ edges }: { edges: BlockedEdge[] }) {
  const data = useMemo(
    () => featureCollection(edges.map((e) => lineFeature(e.geometry, { id: e.edge_id }))),
    [edges],
  )
  useSourceLayers('blocked', data, LAYERS, { belowLabels: true })

  return (
    <>
      {edges.map((e) => (
        <MapMarker key={e.edge_id} lngLat={midpoint(e.geometry)} anchor="bottom">
          <div className="mb-2 flex -translate-x-1/2 items-center gap-1.5 whitespace-nowrap rounded-md border border-red/60 bg-bg/90 px-2 py-1 text-[11px] font-medium text-red backdrop-blur-sm">
            <TriangleAlert className="h-3 w-3" />
            {(REASON_LABEL[e.reason] ?? (() => e.reason))(e.limit)}
          </div>
        </MapMarker>
      ))}
    </>
  )
}
