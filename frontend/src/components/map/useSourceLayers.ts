import { useEffect } from 'react'
import type { GeoJSONSource, LayerSpecification, Map as MlMap } from 'maplibre-gl'
import { useMap } from './context'

/** The layer types we actually use, minus `source` (the hook supplies it). */
export type LayerDef =
  | Omit<Extract<LayerSpecification, { type: 'line' }>, 'source'>
  | Omit<Extract<LayerSpecification, { type: 'circle' }>, 'source'>
  | Omit<Extract<LayerSpecification, { type: 'fill' }>, 'source'>
  | Omit<Extract<LayerSpecification, { type: 'symbol' }>, 'source'>

const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

/** True while the map is mounted and its style is usable. */
export function mapLive(map: MlMap | null): map is MlMap {
  try {
    return !!map && !!map.getStyle()
  } catch {
    return false
  }
}

/** id of the first symbol (label) layer, so overlays sit under place labels */
export function firstSymbolLayerId(map: MlMap): string | undefined {
  return map.getStyle().layers?.find((l) => l.type === 'symbol')?.id
}

/**
 * Attach a GeoJSON source and one or more layers to the map, imperatively.
 * Setup runs once per (map, key); `data` changes are pushed via setData without
 * tearing anything down. `layers` must be a stable reference (module constant).
 */
export function useSourceLayers(
  key: string,
  data: GeoJSON.GeoJSON | null,
  layers: LayerDef[],
  opts?: { belowLabels?: boolean },
) {
  const map = useMap()

  useEffect(() => {
    if (!mapLive(map)) return
    const sourceId = `${key}__src`
    if (!map.getSource(sourceId)) {
      map.addSource(sourceId, { type: 'geojson', data: data ?? EMPTY })
    }
    const beforeId = opts?.belowLabels ? firstSymbolLayerId(map) : undefined
    for (const layer of layers) {
      if (!map.getLayer(layer.id)) {
        map.addLayer({ ...layer, source: sourceId } as LayerSpecification, beforeId)
      }
    }
    return () => {
      if (!mapLive(map)) return
      for (const layer of layers) {
        if (map.getLayer(layer.id)) map.removeLayer(layer.id)
      }
      if (map.getSource(sourceId)) map.removeSource(sourceId)
    }
    // setup is intentionally keyed only on the map + layer key
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, key])

  useEffect(() => {
    if (!mapLive(map)) return
    const src = map.getSource(`${key}__src`) as GeoJSONSource | undefined
    if (src && data) src.setData(data as GeoJSON.FeatureCollection)
  }, [map, key, data])
}
