/* ---------------------------------------------------------------------------
   MARGA frontend configuration. One place to change everything the demo
   depends on: the map area, the API target, the impact assumptions.
--------------------------------------------------------------------------- */

import type { SolverId, VehicleProfile } from '@/types/api'

/**
 * The Bengaluru sub-graph the whole demo centres on.
 *
 * PLACEHOLDER — Koramangala. The backend has not yet locked the real OSMnx
 * sub-graph. When they do, change `center` / `bbox` / `zoom` here and
 * regenerate the mock coordinates (see src/mocks/). Nothing else references
 * hard-coded coordinates.
 */
export const AREA = {
  id: 'bengaluru_koramangala',
  label: 'Koramangala, Bengaluru',
  locked: false,
  center: [77.6309, 12.9352] as [number, number],
  bbox: [77.61, 12.92, 77.652, 12.952] as [number, number, number, number],
  zoom: 13.6,
  minZoom: 11,
  maxZoom: 17,
}

/** Keyless dark base map. Carto Dark Matter — OSM data, no API key, no billing. */
export const MAP_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

/** Mock mode is the default. Set VITE_USE_MOCK=false to hit the real backend. */
export const USE_MOCK = import.meta.env.VITE_USE_MOCK !== 'false'

/** Backend base URL (only used when USE_MOCK is false). Mounts at /api/v1. */
export const API_BASE =
  import.meta.env.VITE_API_BASE ?? 'http://localhost:8000/api/v1'

/**
 * Impact conversion assumptions. These are shown as footnotes in the UI and
 * must never be hidden — an unsourced impact number loses a viva fastest.
 */
export const ASSUMPTIONS = {
  fuelPerKm: 0.32, // litres / km — loaded medium goods vehicle, city cycle
  co2PerLitre: 2.68, // kg CO2 per litre of diesel
  costPerLitre: 94, // INR per litre
  currency: '₹',
  source: 'ARAI city-cycle figures for MGV diesel; placeholder pending team sign-off',
}

/** Default vehicle profile used across the demo unless overridden per screen. */
export const DEFAULT_PROFILE: VehicleProfile = {
  vehicle_class: 'heavy_truck',
  weight_t: 16,
  length_m: 12.2,
  height_m: 4.1,
  width_m: 2.6,
}

/** Solvers offered in the selector. Order matters — baseline first, ours last. */
export const SOLVERS: { id: SolverId; label: string; kind: 'baseline' | 'ours' }[] = [
  { id: 'ortools', label: 'OR-Tools', kind: 'baseline' },
  { id: 'va_qpso', label: 'VA-QPSO', kind: 'ours' },
]

/** QPSO contraction–expansion ceiling, drawn as a reference line on β charts. */
export const BETA_CEILING = 1.781
