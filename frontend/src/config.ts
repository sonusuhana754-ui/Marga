/* ---------------------------------------------------------------------------
   MARGA frontend configuration. One place to change everything the demo
   depends on: the map area, the API target, the impact assumptions.
--------------------------------------------------------------------------- */

import type { SolverId, VehicleProfile } from '@/types/api'

/**
 * The Bengaluru sub-graph the whole demo centres on.
 *
 * PLACEHOLDER — Koramangala. The backend has not yet locked the real OSMnx
 * sub-graph. When it does, change `center` / `bbox` / `zoom` here and move the
 * pins in `src/scene/data/points.json` to match. Nothing else references
 * hard-coded coordinates.
 */
export const AREA = {
  id: 'bengaluru_koramangala',
  /**
   * The backend's graph cache is keyed by *place name*, not by the AREA id, and
   * `POST /api/v1/graphs/load` has to resolve it through OSMnx. Used only by the
   * single-vehicle route call.
   */
  place: 'Koramangala, Bengaluru, India',
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
