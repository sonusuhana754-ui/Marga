import { useMemo } from 'react'
import type { LngLat } from '@/types/api'
import { featureCollection, pointFeature } from '@/lib/geo'
import { useSourceLayers } from './useSourceLayers'
import type { LayerDef } from './useSourceLayers'
import { MapMarker } from './MapMarker'

const STOP_LAYERS: LayerDef[] = [
  {
    id: 'stops-halo',
    type: 'circle',
    paint: {
      'circle-radius': 7,
      'circle-color': '#2fd9c4',
      'circle-opacity': 0.14,
    },
  },
  {
    id: 'stops-dot',
    type: 'circle',
    paint: {
      'circle-radius': 3.5,
      'circle-color': '#0b1416',
      'circle-stroke-color': '#8fe6db',
      'circle-stroke-width': 1.75,
    },
  },
]

interface WaypointsProps {
  depot: LngLat
  stops: LngLat[]
}

export function Waypoints({ depot, stops }: WaypointsProps) {
  const data = useMemo(
    () => featureCollection(stops.map((s, i) => pointFeature(s, { i }))),
    [stops],
  )
  useSourceLayers('stops', data, STOP_LAYERS, { belowLabels: true })

  return (
    <MapMarker lngLat={depot} anchor="center">
      <div className="flex -translate-y-1/2 items-center gap-2">
        <span className="relative flex h-3.5 w-3.5 items-center justify-center">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber/40" />
          <span className="relative h-2.5 w-2.5 rounded-full border-2 border-amber bg-bg" />
        </span>
        <span className="label-mono !text-[9.5px] !tracking-[0.16em] !text-amber">
          Depot
        </span>
      </div>
    </MapMarker>
  )
}
