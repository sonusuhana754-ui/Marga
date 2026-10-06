import type { BenchmarkResponse, BenchmarkResult, SolverId } from '@/types/api'
import { API_BASE } from '@/config'

/**
 * The scenarios `backend/app/algorithms/scenarios.py` registers — the only
 * ones the benchmark endpoint will accept. Kept here (rather than fetched)
 * because the backend has no scenario-listing endpoint; the ids are mirrored
 * by hand and `BenchmarkView` renders a 422 verbatim if they ever drift.
 *
 * The 6- and 8-node instances are kept because the backend's test suite pins
 * them, but they are flagged "too small to rank solvers" in the UI: at 5-7
 * stops every solver reaches the optimum and all rows tie.
 */
export const BENCHMARK_SCENARIOS: readonly string[] = [
  'grid_cvrp_25',
  'grid_cvrp_49',
  'grid_vrptw_25',
  'grid_cvrp_8',
  'grid_cvrp_6',
  'grid_vrptw_8',
]

/** Scenarios big enough for a quality comparison to mean anything. */
export const RANKABLE_BENCHMARK_SCENARIOS: readonly string[] = [
  'grid_cvrp_25',
  'grid_cvrp_49',
  'grid_vrptw_25',
]

const SOLVERS: SolverId[] = ['ortools', 'qpso', 'va_qpso']

/**
 * POST /benchmark — repeated-run solver comparison.
 *
 * Every number in the response is measured while handling the request: the
 * backend runs each solver `repeats` times on a deterministic in-code scenario
 * and reports best cost, gap, and runtime spread. There is no fixture path, so
 * a failure surfaces as an error in the view instead of synthetic rows.
 */
export async function getBenchmark(
  scenarioId: string,
  repeats = 1,
): Promise<BenchmarkResponse> {
  const res = await fetch(`${API_BASE}/benchmark`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_id: scenarioId, repeats, solvers: SOLVERS }),
  })
  if (!res.ok) {
    let detail = ''
    try {
      const body = (await res.json()) as { detail?: unknown }
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail ?? '')
    } catch {
      /* non-JSON error body */
    }
    throw new Error(detail || `benchmark failed: ${res.status}`)
  }
  const body = await res.json()

  // The backend sends a real per-solver convergence trace for the arms that
  // have one; OR-Tools sends an empty list. Normalise the optional collections
  // defensively and leave the traces exactly as measured.
  const results: BenchmarkResult[] = body.results.map((r: BenchmarkResult) => ({
    ...r,
    convergence: r.convergence ?? [],
    runs: r.runs ?? [],
    violations: r.violations ?? [],
  }))

  return { ...body, results, source: 'backend' }
}
