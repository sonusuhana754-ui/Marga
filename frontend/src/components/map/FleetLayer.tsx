import { useEffect, useMemo } from 'react'
import type { MapLayerMouseEvent } from 'maplibre-gl'
import type { FleetRoute } from '@/types/api'
import { featureCollection, lineFeature } from '@/lib/geo'
import { vehicleColor } from '@/lib/palette'
import { boundsOf, FIT_PADDING } from '@/lib/bounds'
import { useMap } from './context'
import { mapLive, useSourceLayers } from './useSourceLayers'
import type { LayerDef } from './useSourceLayers'

const LAYERS: LayerDef[] = [
  {
    id: 'fleet-glow',
    type: 'line',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': ['get', 'color'],
      'line-width': 12,
      'line-opacity': 0.14,
      'line-blur': 8,
    },
  },
  {
    id: 'fleet-line',
    type: 'line',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: {
      'line-color': ['get', 'color'],
      'line-width': 3.4,
      'line-opacity': 0.92,
    },
  },
  {
    // invisible wide hit-target so a route is easy to click
    id: 'fleet-hit',
    type: 'line',
    layout: { 'line-cap': 'round', 'line-join': 'round' },
    paint: { 'line-color': '#000000', 'line-opacity': 0, 'line-width': 22 },
  },
]

interface FleetLayerProps {
  routes: FleetRoute[]
  selected: number | null
  onSelect: (id: number | null) => void
}

export function FleetLayer({ routes, selected, onSelect }: FleetLayerProps) {
  const map = useMap()

  const data = useMemo(
    () =>
      featureCollection(
        routes.map((r) =>
          lineFeature(r.path, { vehicle_id: r.vehicle_id, color: vehicleColor(r.vehicle_id) }),
        ),
      ),
    [routes],
  )

  useSourceLayers('fleet', data, LAYERS, { belowLabels: true })

  // frame the whole fleet when a new result arrives
  useEffect(() => {
    if (!mapLive(map)) return
    const b = boundsOf(routes.map((r) => r.path))
    if (b) map.fitBounds(b, { padding: FIT_PADDING, duration: 700, maxZoom: 15 })
  }, [map, routes])

  // click + hover on the wide invisible hit layer.
  // `data` is in the deps so this re-binds after the layer is (re)added.
  useEffect(() => {
    if (!mapLive(map) || !map.getLayer('fleet-hit')) return
    const onClick = (e: MapLayerMouseEvent) => {
      const id = e.features?.[0]?.properties?.vehicle_id
      if (typeof id === 'number') onSelect(id)
    }
    const enter = () => {
      map.getCanvas().style.cursor = 'pointer'
    }
    const leave = () => {
      map.getCanvas().style.cursor = ''
    }
    map.on('click', 'fleet-hit', onClick)
    map.on('mouseenter', 'fleet-hit', enter)
    map.on('mouseleave', 'fleet-hit', leave)
    return () => {
      map.off('click', 'fleet-hit', onClick)
      map.off('mouseenter', 'fleet-hit', enter)
      map.off('mouseleave', 'fleet-hit', leave)
    }
  }, [map, onSelect, data])

  // dim non-selected routes
  useEffect(() => {
    if (!mapLive(map) || !map.getLayer('fleet-line')) return
    map.setPaintProperty(
      'fleet-line',
      'line-opacity',
      selected === null
        ? 0.92
        : ['case', ['==', ['get', 'vehicle_id'], selected], 1, 0.14],
    )
    map.setPaintProperty(
      'fleet-glow',
      'line-opacity',
      selected === null
        ? 0.14
        : ['case', ['==', ['get', 'vehicle_id'], selected], 0.26, 0.03],
    )
  }, [map, selected, data])

  return null
}
