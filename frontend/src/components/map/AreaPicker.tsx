import { useEffect } from 'react'
import { useDemo } from '@/state/demoStore'
import { useMap } from './context'

/**
 * Click-to-load area picker.
 *
 * Mounted inside the map canvas. While "pick a place" is armed, a click sends
 * those coordinates to the backend, which downloads the real OSM road network
 * around them — any point on Earth, no place name required.
 */
export function AreaPicker() {
  const map = useMap()
  const { picking, loadAreaByPoint } = useDemo()

  useEffect(() => {
    if (!picking || !map) return

    const canvas = map.getCanvas()
    const previousCursor = canvas.style.cursor
    canvas.style.cursor = 'crosshair'

    const onClick = (e: { lngLat: { lng: number; lat: number } }) => {
      void loadAreaByPoint([e.lngLat.lng, e.lngLat.lat])
    }
    map.on('click', onClick)

    return () => {
      map.off('click', onClick)
      canvas.style.cursor = previousCursor
    }
  }, [map, picking, loadAreaByPoint])

  return null
}

/**
 * Frames the loaded area as soon as it arrives, so loading a new place is
 * visibly reflected on the map instead of leaving the view where it was.
 */
export function AreaFramer() {
  const map = useMap()
  const { area } = useDemo()

  useEffect(() => {
    if (!area || !map) return
    if (area.bounds) {
      const [minLng, minLat, maxLng, maxLat] = area.bounds
      map.fitBounds(
        [
          [minLng, minLat],
          [maxLng, maxLat],
        ],
        { padding: 64, duration: 900, maxZoom: 16 },
      )
    } else if (area.center) {
      map.easeTo({ center: area.center, zoom: 14, duration: 900 })
    }
  }, [map, area])

  return null
}
