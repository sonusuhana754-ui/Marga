import type { ImpactFigures, LngLat, RouteResponse } from '@/types/api'
import points from './data/points.json'
import singleRoute from './data/single-route.json'

/**
 * Anchor points are hand-authored in data/points.json; the road-following route
 * geometry (single-route.json, fleet-*.json) is generated from them by
 * `npm run gen:mocks`. Re-run that after the backend locks the real sub-graph.
 */
export const DEPOT = points.depot as unknown as LngLat
export const STOPS = points.stops as unknown as LngLat[]

export const mockSingleRoute = singleRoute as unknown as RouteResponse

/**
 * Sample fleet-level impact for the bottom strip. Placeholder until a real
 * /optimize run measures it — flagged `measured: false` so the UI says so.
 */
export const mockImpactSample: ImpactFigures = {
  time_saved_s: 4380,
  fuel_saved_l: 34.2,
  co2_saved_kg: 91.7,
  distance_saved_m: 52_300,
  measured: false,
}
