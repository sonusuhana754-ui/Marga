import type { BenchmarkResponse, ConvergencePoint, SolverId } from '@/types/api'

/** Exponential-decay convergence curve from `start` down to `final`. */
function convergence(start: number, final: number, iterations: number): ConvergencePoint[] {
  return Array.from({ length: iterations }, (_, i) => {
    const t = iterations > 1 ? i / (iterations - 1) : 1
    return {
      iteration: i,
      best_cost: Math.round(final + (start - final) * Math.exp(-3.6 * t)),
    }
  })
}

interface Row {
  solver: SolverId
  gap_pct: number
  runtime_ms: number
  iters: number
}

interface Instance {
  best_known: number
  rows: Row[]
}

/**
 * Mock benchmark results. Deliberately NOT rigged for VA-QPSO:
 *  - X-n101-k25: OR-Tools wins clearly (small static instance)
 *  - X-n200-k36: near tie, VA-QPSO edges it
 *  - bengaluru-live: VA-QPSO wins (its traffic-aware search pays off)
 * Real numbers from the backend's benchmark runner replace all of this.
 */
const INSTANCES: Record<string, Instance> = {
  'X-n101-k25': {
    best_known: 27591,
    rows: [
      { solver: 'ortools', gap_pct: 1.8, runtime_ms: 60000, iters: 24 },
      { solver: 'va_qpso', gap_pct: 3.4, runtime_ms: 4200, iters: 60 },
      { solver: 'qpso', gap_pct: 5.1, runtime_ms: 3800, iters: 60 },
      { solver: 'ga', gap_pct: 6.2, runtime_ms: 8100, iters: 80 },
      { solver: 'aco', gap_pct: 7.0, runtime_ms: 12400, iters: 80 },
      { solver: 'pso', gap_pct: 8.4, runtime_ms: 3500, iters: 60 },
    ],
  },
  'X-n200-k36': {
    best_known: 58578,
    rows: [
      { solver: 'va_qpso', gap_pct: 4.1, runtime_ms: 9800, iters: 90 },
      { solver: 'ortools', gap_pct: 4.4, runtime_ms: 60000, iters: 30 },
      { solver: 'qpso', gap_pct: 6.0, runtime_ms: 8200, iters: 90 },
      { solver: 'ga', gap_pct: 7.1, runtime_ms: 15200, iters: 110 },
      { solver: 'aco', gap_pct: 8.0, runtime_ms: 22600, iters: 110 },
      { solver: 'pso', gap_pct: 9.5, runtime_ms: 7000, iters: 90 },
    ],
  },
  'bengaluru-live': {
    best_known: 17120,
    rows: [
      { solver: 'va_qpso', gap_pct: 1.9, runtime_ms: 2140, iters: 64 },
      { solver: 'qpso', gap_pct: 2.9, runtime_ms: 1900, iters: 64 },
      { solver: 'ortools', gap_pct: 6.8, runtime_ms: 760, iters: 22 },
      { solver: 'ga', gap_pct: 9.2, runtime_ms: 5000, iters: 80 },
      { solver: 'pso', gap_pct: 12.1, runtime_ms: 1600, iters: 64 },
      { solver: 'aco', gap_pct: 11.0, runtime_ms: 8000, iters: 80 },
    ],
  },
}

export const BENCHMARK_INSTANCES = Object.keys(INSTANCES)

export function mockBenchmark(instance: string): BenchmarkResponse {
  const inst = INSTANCES[instance] ?? INSTANCES[BENCHMARK_INSTANCES[0]]
  return {
    instance,
    best_known: inst.best_known,
    results: inst.rows.map((r) => {
      const cost = Math.round(inst.best_known * (1 + r.gap_pct / 100))
      return {
        solver: r.solver,
        cost,
        gap_pct: r.gap_pct,
        runtime_ms: r.runtime_ms,
        convergence: convergence(Math.round(cost * 1.42), cost, r.iters),
      }
    }),
  }
}
