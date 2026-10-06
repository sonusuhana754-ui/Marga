import { createContext, useContext } from 'react'
import type { Map as MlMap } from 'maplibre-gl'

export const MapContext = createContext<MlMap | null>(null)

/** The MapLibre instance, or null until its style has loaded. */
export function useMap(): MlMap | null {
  return useContext(MapContext)
}
