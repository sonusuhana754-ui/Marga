import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { OptimizeResponse, SolverId } from '@/types/api'
import { runOptimize } from '@/api/optimize'
import { AREA, DEFAULT_PROFILE } from '@/config'
import { mockSingleRoute } from '@/mocks'
import { DemoCtx } from './demoStore'
import type { DemoValue, Mode } from './demoStore'

export function DemoProvider({ children }: { children: ReactNode }) {
  const [mode, setModeRaw] = useState<Mode>('fleet')
  const [solver, setSolver] = useState<SolverId>('va_qpso')
  const [status, setStatus] = useState<DemoValue['status']>('idle')
  const [runs, setRuns] = useState<Partial<Record<SolverId, OptimizeResponse>>>({})
  const [selectedVehicle, setSelectedVehicle] = useState<number | null>(null)

  const optimize = useCallback(async () => {
    setStatus('optimizing')
    setSelectedVehicle(null)
    const base = {
      city: AREA.id,
      vehicles: 2,
      vehicle_profile: DEFAULT_PROFILE,
      capacity: 100,
      stops: 10,
      seed: 42,
    }
    const [ours, baseline] = await Promise.all([
      runOptimize({ ...base, solver: 'va_qpso' }),
      runOptimize({ ...base, solver: 'ortools' }),
    ])
    setRuns({ va_qpso: ours, ortools: baseline })
    setStatus('ready')
  }, [])

  const setMode = useCallback((m: Mode) => {
    setModeRaw(m)
    setSelectedVehicle(null)
  }, [])

  const reset = useCallback(() => {
    setRuns({})
    setStatus('idle')
    setSelectedVehicle(null)
  }, [])

  const selectVehicle = useCallback((id: number | null) => setSelectedVehicle(id), [])

  const value = useMemo<DemoValue>(
    () => ({
      mode,
      solver,
      status,
      runs,
      activeRun: runs[solver] ?? null,
      single: mockSingleRoute,
      selectedVehicle,
      setMode,
      setSolver,
      optimize,
      selectVehicle,
      reset,
    }),
    [mode, solver, status, runs, selectedVehicle, setMode, optimize, selectVehicle, reset],
  )

  return <DemoCtx.Provider value={value}>{children}</DemoCtx.Provider>
}
