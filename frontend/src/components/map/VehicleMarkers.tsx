import { useEffect } from 'react'
import type { GeoJSONSource } from 'maplibre-gl'
import type { FleetRoute } from '@/types/api'
import { featureCollection, pointFeature, positionAtTime } from '@/lib/geo'
import { vehicleColor } from '@/lib/palette'
import { useSimClock } from '@/state/simClock'
import { useMap } from './context'
import { mapLive } from './useSourceLayers'

const SRC = 'vehicles__src'

/**
 * Animated vehicle dots. Positions are recomputed every frame from the sim
 * clock and pushed to a GeoJSON source imperatively — React never re-renders
 * per frame.
 */
export function VehicleMarkers({ routes, selected }: { routes: FleetRoute[]; selected: number | null }) {
  const map = useMap()
  const clock = useSimClock()

  useEffect(() => {
    if (!mapLive(map)) return

    const build = (t: number) =>
      featureCollection(
        routes.map((r) =>
          pointFeature(positionAtTime(r.path, r.timestamps, t), {
            vehicle_id: r.vehicle_id,
            color: vehicleColor(r.vehicle_id),
          }),
        ),
      )

    if (!map.getSource(SRC)) {
      map.addSource(SRC, { type: 'geojson', data: build(clock.getTime()) })
    }
    if (!map.getLayer('vehicles-halo')) {
      map.addLayer({
        id: 'vehicles-halo',
        type: 'circle',
        source: SRC,
        paint: {
          'circle-radius': 11,
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.2,
          'circle-blur': 0.4,
        },
      })
    }
    if (!map.getLayer('vehicles-dot')) {
      map.addLayer({
        id: 'vehicles-dot',
        type: 'circle',
        source: SRC,
        paint: {
          'circle-radius': 5,
          'circle-color': ['get', 'color'],
          'circle-stroke-color': '#04211e',
          'circle-stroke-width': 2,
        },
      })
    }

    const unsub = clock.subscribe((t) => {
      const src = map.getSource(SRC) as GeoJSONSource | undefined
      if (src) src.setData(build(t) as GeoJSON.FeatureCollection)
    })

    return () => {
      unsub()
      if (!mapLive(map)) return
      for (const id of ['vehicles-halo', 'vehicles-dot']) {
        if (map.getLayer(id)) map.removeLayer(id)
      }
      if (map.getSource(SRC)) map.removeSource(SRC)
    }
  }, [map, routes, clock])

  // fade non-selected vehicle dots in sync with the routes
  useEffect(() => {
    if (!mapLive(map) || !map.getLayer('vehicles-dot')) return
    const op =
      selected === null ? 1 : ['case', ['==', ['get', 'vehicle_id'], selected], 1, 0.2]
    map.setPaintProperty('vehicles-dot', 'circle-opacity', op)
    map.setPaintProperty(
      'vehicles-halo',
      'circle-opacity',
      selected === null ? 0.2 : ['case', ['==', ['get', 'vehicle_id'], selected], 0.28, 0.04],
    )
  }, [map, selected])

  return null
}
