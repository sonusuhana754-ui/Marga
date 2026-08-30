import type {
  ConvergencePoint,
  FleetRoute,
  OptimizeResponse,
  SolverId,
} from '@/types/api'
import { ASSUMPTIONS } from '@/config'
import vaqpso from './data/fleet-va_qpso.json'
import ortools from './data/fleet-ortools.json'

const ROUTES: Record<'va_qpso' | 'ortools', FleetRoute[]> = {
  va_qpso: vaqpso as unknown as FleetRoute[],
  ortools: ortools as unknown as FleetRoute[],
}

function totalDistance(routes: FleetRoute[]): number {
  return routes.reduce((s, r) => s + r.distance_m, 0)
}

/** Exponential-decay convergence curve from `start` down to `end`. */
function convergence(start: number, end: number, iterations: number): ConvergencePoint[] {
  return Array.from({ length: iterations }, (_, i) => {
    const t = iterations > 1 ? i / (iterations - 1) : 1
    return {
      iteration: i,
      best_cost: Math.round(end + (start - end) * Math.exp(-3.4 * t)),
    }
  })
}

/**
 * A mock /optimize response for the live Bengaluru scenario.
 *
 * On THIS instance VA-QPSO edges out OR-Tools on cost (its traffic-aware search
 * pays off here) while OR-Tools is far quicker. The Benchmark Lab shows the
 * flip side — standard CVRPLIB instances where OR-Tools wins. Real numbers
 * replace all of this once the backend runs.
 */
export function mockOptimize(solver: SolverId): OptimizeResponse {
  const key: 'va_qpso' | 'ortools' = solver === 'va_qpso' ? 'va_qpso' : 'ortools'
  const routes = ROUTES[key]
  const cost = totalDistance(routes)
  const ours = key === 'va_qpso'

  // Coherent impact: every figure derives from the actual distance delta and
  // the documented assumptions in config.ts — nothing invented.
  const distanceSaved = totalDistance(ROUTES.ortools) - totalDistance(ROUTES.va_qpso)
  const km = distanceSaved / 1000
  const fuelSaved = km * ASSUMPTIONS.fuelPerKm
  const impact = ours
    ? {
        time_saved_s: Math.round((km / 18) * 3600), // ~18 km/h effective city speed
        fuel_saved_l: Number(fuelSaved.toFixed(1)),
        co2_saved_kg: Number((fuelSaved * ASSUMPTIONS.co2PerLitre).toFixed(1)),
        distance_saved_m: Math.round(distanceSaved),
        measured: false,
      }
    : {
        time_saved_s: 0,
        fuel_saved_l: 0,
        co2_saved_kg: 0,
        distance_saved_m: 0,
        measured: false,
      }

  return {
    run_id: `r_${key}_mock`,
    solver,
    total_cost: cost,
    runtime_ms: ours ? 2140 : 760,
    vehicles_used: routes.length,
    routes,
    convergence: convergence(cost * 1.4, cost, ours ? 64 : 38),
    impact,
  }
}
