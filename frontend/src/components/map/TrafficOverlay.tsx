import { useMemo } from 'react'
import type { StreamTick } from '@/types/api'
import { mockGraph } from '@/mocks'
import { featureCollection, lineFeature } from '@/lib/geo'
import { useSourceLayers } from './useSourceLayers'
import type { LayerDef } from './useSourceLayers'

const LAYERS: LayerDef[] = [
  {
    id: 'traffic-line',
    type: 'line',
    layout: { 'line-cap': 'round' },
    paint: {
      'line-color': [
        'match',
        ['get', 'level'],
        'heavy',
        '#ee6b4d',
        'moderate',
        '#e9b23c',
        '#3a4a4e',
      ],
      'line-width': ['match', ['get', 'level'], 'heavy', 4, 'moderate', 3, 1.5],
      'line-opacity': ['match', ['get', 'level'], 'free', 0, 0.8],
    },
  },
]

const EDGE_GEOM = new Map(mockGraph.edges.map((e) => [e.edge_id, e.geometry]))

/** Background (external) traffic congestion on the road network. */
export function TrafficOverlay({ tick }: { tick: StreamTick | null }) {
  const data = useMemo(
    () =>
      featureCollection(
        (tick?.background_traffic ?? [])
          .filter((c) => EDGE_GEOM.has(c.edge_id))
          .map((c) => lineFeature(EDGE_GEOM.get(c.edge_id)!, { level: c.level })),
      ),
    [tick],
  )

  useSourceLayers('traffic', data, LAYERS, { belowLabels: true })
  return null
}
