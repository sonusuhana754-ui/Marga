import { useEffect, useMemo } from 'react'
import type { LngLat } from '@/types/api'
import { featureCollection, lineFeature } from '@/lib/geo'
import { boundsOf, FIT_PADDING } from '@/lib/bounds'
import { useMap } from './context'
import { mapLive, useSourceLayers } from './useSourceLayers'
import type { LayerDef } from './useSourceLayers'

const LAYERS: LayerDef[] = [
  {
    id: 'route-alt-casing',
    type: 'line',
    filter: ['==', ['get', 'kind'], 'alt'],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#090e10', 'line-width': 5, 'line-opacity': 0.6 },
  },
  {
    id: 'route-alt',
    type: 'line',
    filter: ['==', ['get', 'kind'], 'alt'],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#aab8bb',
      'line-width': 2.5,
      'line-opacity': 0.8,
      'line-dasharray': [2, 1.8],
    },
  },
  {
    id: 'route-best-glow',
    type: 'line',
    filter: ['==', ['get', 'kind'], 'best'],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': '#2fd9c4',
      'line-width': 16,
      'line-opacity': 0.16,
      'line-blur': 10,
    },
  },
  {
    id: 'route-best',
    type: 'line',
    filter: ['==', ['get', 'kind'], 'best'],
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#2fd9c4', 'line-width': 4, 'line-opacity': 0.95 },
  },
]

interface RouteLayerProps {
  best: LngLat[]
  /** the shorter, rejected alternative — drawn dim and dashed */
  alternative?: LngLat[]
}

export function RouteLayer({ best, alternative }: RouteLayerProps) {
  const data = useMemo(() => {
    const feats: GeoJSON.Feature<GeoJSON.LineString, { kind: 'best' | 'alt' }>[] = [
      lineFeature(best, { kind: 'best' }),
    ]
    if (alternative) feats.unshift(lineFeature(alternative, { kind: 'alt' }))
    return featureCollection(feats)
  }, [best, alternative])

  useSourceLayers('routes', data, LAYERS, { belowLabels: true })

  const map = useMap()
  useEffect(() => {
    if (!mapLive(map)) return
    const b = boundsOf(alternative ? [best, alternative] : [best])
    if (b) map.fitBounds(b, { padding: FIT_PADDING, duration: 700, maxZoom: 15 })
  }, [map, best, alternative])

  return null
}
