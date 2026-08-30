import { createContext, useContext } from 'react'
import type { OptimizeResponse, RouteResponse, SolverId } from '@/types/api'

export type Mode = 'single' | 'fleet'
export type Status = 'idle' | 'optimizing' | 'ready'

export interface DemoValue {
  mode: Mode
  solver: SolverId
  status: Status
  /** both solver results, populated together on optimize() */
  runs: Partial<Record<SolverId, OptimizeResponse>>
  /** the run currently drawn on the map (per `solver`) */
  activeRun: OptimizeResponse | null
  single: RouteResponse
  selectedVehicle: number | null

  setMode: (m: Mode) => void
  setSolver: (s: SolverId) => void
  optimize: () => Promise<void>
  selectVehicle: (id: number | null) => void
  reset: () => void
}

export const DemoCtx = createContext<DemoValue | null>(null)

export function useDemo(): DemoValue {
  const v = useContext(DemoCtx)
  if (!v) throw new Error('useDemo must be used inside <DemoProvider>')
  return v
}
