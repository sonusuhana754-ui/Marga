import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { createPortal } from 'react-dom'
import maplibregl from 'maplibre-gl/dist/maplibre-gl-csp'
import type { LngLat } from '@/types/api'
import { useMap } from './context'

interface MapMarkerProps {
  lngLat: LngLat
  children: ReactNode
  anchor?: 'center' | 'top' | 'bottom' | 'left' | 'right'
}

/** Renders React content at a geographic point via a MapLibre Marker + portal. */
export function MapMarker({ lngLat, children, anchor = 'center' }: MapMarkerProps) {
  const map = useMap()
  const [el] = useState(() => {
    const d = document.createElement('div')
    d.style.willChange = 'transform'
    return d
  })

  useEffect(() => {
    if (!map) return
    const marker = new maplibregl.Marker({ element: el, anchor }).setLngLat(lngLat).addTo(map)
    return () => {
      try {
        marker.remove()
      } catch {
        /* map already torn down */
      }
    }
  }, [map, el, anchor, lngLat])

  return createPortal(children, el)
}
