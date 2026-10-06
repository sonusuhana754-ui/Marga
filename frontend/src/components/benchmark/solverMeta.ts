import type { SolverId } from '@/types/api'

export const SOLVER_META: Record<string, { label: string; color: string }> = {
  va_qpso: { label: 'VA-QPSO', color: '#2fd9c4' },
  qpso: { label: 'QPSO', color: '#6e93e6' },
  ortools: { label: 'OR-Tools', color: '#e8a24a' },
  ga: { label: 'GA', color: '#9ad17f' },
  aco: { label: 'ACO', color: '#d46fb8' },
  pso: { label: 'PSO', color: '#7fa9d9' },
  dijkstra: { label: 'Dijkstra', color: '#8fa2a5' },
}

export const solverLabel = (s: SolverId) => SOLVER_META[s]?.label ?? s
export const solverColor = (s: SolverId) => SOLVER_META[s]?.color ?? '#8fa2a5'
