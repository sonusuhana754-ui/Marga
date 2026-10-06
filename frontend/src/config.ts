/* ---------------------------------------------------------------------------
   MARGA frontend configuration. One place to change everything the demo
   depends on: the map area, the API target, the impact assumptions.
--------------------------------------------------------------------------- */

import type { SolverId, VehicleProfile } from '@/types/api'

/**
 * Where the map *opens* — and how far the default area download reaches.
 *
 * This is an initial view, not a boundary: the canvas has no maxBounds, so the
 * user can pan anywhere on Earth and the backend will fetch whatever road
 * network they point at. `place` is only the fallback label for the
 * single-vehicle call; `center`/`dist_m` is the default download target when a
 * run needs a graph and none has been chosen yet.
 */
export const AREA = {
  id: 'bengaluru_koramangala',
  /** Default place name, used when a named load is wanted over a point load. */
  place: 'Koramangala, Bengaluru, India',
  label: 'Koramangala, Bengaluru',
  locked: false,
  /** Default download target: [lng, lat] and radius in metres. */
  center: [77.6309, 12.9352] as [number, number],
  dist_m: 1200,
  /** Reference extent for the opening frame only. */
  bbox: [77.61, 12.92, 77.652, 12.952] as [number, number, number, number],
  zoom: 13.6,
  minZoom: 2,
  maxZoom: 18,
}

/** Keyless dark base map. Carto Dark Matter — OSM data, no API key, no billing. */
export const MAP_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

/**
 * Backend base URL. Every request the UI makes goes here — there is no fixture
 * mode and no silent fallback, so if this is wrong the screens say so instead
 * of inventing numbers. Mounts at /api/v1.
 */
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

/**
 * Solvers the FastAPI backend genuinely implements, i.e. what
 * `app/algorithms/registry.py` can run: the OR-Tools baseline, fixed-schedule
 * QPSO, and volatility-adaptive VA-QPSO.
 *
 * All three are listed because all three now exist. `qpso` is included on
 * purpose even though it is not the headline algorithm: the design doc's ablation
 * is invalid without a fixed-β anchor, so the UI can compare the contribution
 * against the algorithm it extends. There is still no GA / ACO / PSO
 * implementation in the backend, so those are not offered.
 */
export const LIVE_SOLVERS: SolverId[] = ['ortools', 'qpso', 'va_qpso']

/** All solvers the UI knows about. Baseline first, ours last. */
const ALL_SOLVERS: { id: SolverId; label: string; kind: 'baseline' | 'ours' }[] = [
  { id: 'ortools', label: 'OR-Tools', kind: 'baseline' },
  { id: 'qpso', label: 'QPSO (fixed β)', kind: 'baseline' },
  { id: 'va_qpso', label: 'VA-QPSO', kind: 'ours' },
]

/** Selectable solvers: exactly what the backend can run. */
export const SOLVERS = ALL_SOLVERS.filter((s) => LIVE_SOLVERS.includes(s.id))

/**
 * The solver the dashboard opens with. VA-QPSO — it is implemented now, so
 * there is no reason to open on the baseline and hide it behind a tab.
 */
export const DEFAULT_SOLVER: SolverId = 'va_qpso'

/** QPSO contraction–expansion ceiling, drawn as a reference line on β charts. */
export const BETA_CEILING = 1.781
