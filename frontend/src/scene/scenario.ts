import type { LngLat } from '@/types/api'
import points from './data/points.json'

/**
 * Hand-authored anchor coordinates in data/points.json — the depot and the
 * delivery stops the demo draws. This is *scene* data, not results: it says
 * where things are, never what any solver computed.
 */
export const DEPOT = points.depot as unknown as LngLat
export const STOPS = points.stops as unknown as LngLat[]
