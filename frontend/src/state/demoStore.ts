import { createContext, useContext } from 'react'
import type { BetaPoint, OptimizeResponse, RouteResponse, SolverId } from '@/types/api'

export type Mode = 'single' | 'fleet'
export type Status = 'idle' | 'optimizing' | 'ready' | 'error'
export type View = 'live' | 'benchmark'

export interface DemoValue {
  view: View
  guided: boolean
  mode: Mode
  solver: SolverId
  status: Status
  /** Message when `status === 'error'`. Empty otherwise. */
  error: string
  /** both solver results, populated together on optimize() */
  runs: Partial<Record<SolverId, OptimizeResponse>>
  /** the run currently drawn on the map (per `solver`) */
  activeRun: OptimizeResponse | null
  /**
   * Measured β, one point per solver iteration, for the active run. Null when
   * the run reported no β history — OR-Tools has none — so the β panel is
   * hidden instead of showing a curve for a solver that produced none.
   */
  betaSeries: BetaPoint[] | null
  /**
   * Single-vehicle route. Null until `POST /route` answers, and it stays null
   * with `singleError` set when the backend has no loaded graph.
   */
  single: RouteResponse | null
  singleError: string | null
  selectedVehicle: number | null

  setView: (v: View) => void
  setGuided: (g: boolean) => void
  setMode: (m: Mode) => void
  setSolver: (s: SolverId) => void
  optimize: () => Promise<void>
  /** Load the OSM graph server-side, then retry the single-vehicle route. */
  retrySingle: () => Promise<void>
  selectVehicle: (id: number | null) => void
  reset: () => void
}

export const DemoCtx = createContext<DemoValue | null>(null)

export function useDemo(): DemoValue {
  const v = useContext(DemoCtx)
  if (!v) throw new Error('useDemo must be used inside <DemoProvider>')
  return v
}
