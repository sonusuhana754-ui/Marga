import { useMemo } from 'react'
import type { StreamTick } from '@/types/api'
import { featureCollection, lineFeature } from '@/lib/geo'
import { ROAD_SEGMENT_GEOM } from '@/mocks/roads'
import { useSourceLayers } from './useSourceLayers'
import type { LayerDef } from './useSourceLayers'

const LAYERS: LayerDef[] = [
  {
    id: 'traffic-glow',
    type: 'line',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': ['match', ['get', 'level'], 'heavy', '#ee6b4d', '#e9b23c'],
      'line-width': ['match', ['get', 'level'], 'heavy', 13, 'moderate', 9, 0],
      'line-blur': 6,
      'line-opacity': ['match', ['get', 'level'], 'free', 0, 'heavy', 0.5, 0.32],
    },
  },
  {
    id: 'traffic-line',
    type: 'line',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': ['match', ['get', 'level'], 'heavy', '#ee6b4d', '#e9b23c'],
      'line-width': ['match', ['get', 'level'], 'heavy', 3.5, 'moderate', 2.5, 0],
      'line-opacity': ['match', ['get', 'level'], 'free', 0, 0.85],
    },
  },
]

/** Background (external) traffic congestion on the road network. */
export function TrafficOverlay({ tick }: { tick: StreamTick | null }) {
  const data = useMemo(
    () =>
      featureCollection(
        (tick?.background_traffic ?? [])
          .filter((c) => ROAD_SEGMENT_GEOM.has(c.edge_id))
          .map((c) => lineFeature(ROAD_SEGMENT_GEOM.get(c.edge_id)!, { level: c.level })),
      ),
    [tick],
  )

  useSourceLayers('traffic', data, LAYERS, { belowLabels: true })
  return null
}
