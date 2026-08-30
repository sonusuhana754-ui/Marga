import { useCallback, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import type { OptimizeResponse, SolverId, StreamTick } from '@/types/api'
import { runOptimize } from '@/api/optimize'
import { getStream } from '@/api/stream'
import { AREA, DEFAULT_PROFILE } from '@/config'
import { mockSingleRoute } from '@/mocks'
import { DemoCtx } from './demoStore'
import type { DemoValue, Mode, View } from './demoStore'

const runDuration = (r: OptimizeResponse) =>
  r.routes.reduce((m, route) => Math.max(m, route.timestamps.at(-1) ?? 0), 0)

export function DemoProvider({ children }: { children: ReactNode }) {
  const [view, setView] = useState<View>('live')
  const [mode, setModeRaw] = useState<Mode>('fleet')
  const [solver, setSolver] = useState<SolverId>('va_qpso')
  const [status, setStatus] = useState<DemoValue['status']>('idle')
  const [runs, setRuns] = useState<Partial<Record<SolverId, OptimizeResponse>>>({})
  const [stream, setStream] = useState<StreamTick[] | null>(null)
  const [selectedVehicle, setSelectedVehicle] = useState<number | null>(null)

  const optimize = useCallback(async () => {
    setStatus('optimizing')
    setSelectedVehicle(null)
    setStream(null)
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
    getStream(ours.run_id, runDuration(ours)).then(setStream)
  }, [])

  const setMode = useCallback((m: Mode) => {
    setModeRaw(m)
    setSelectedVehicle(null)
  }, [])

  const reset = useCallback(() => {
    setRuns({})
    setStream(null)
    setStatus('idle')
    setSelectedVehicle(null)
  }, [])

  const selectVehicle = useCallback((id: number | null) => setSelectedVehicle(id), [])

  const value = useMemo<DemoValue>(
    () => ({
      view,
      mode,
      solver,
      status,
      runs,
      activeRun: runs[solver] ?? null,
      stream,
      single: mockSingleRoute,
      selectedVehicle,
      setView,
      setMode,
      setSolver,
      optimize,
      selectVehicle,
      reset,
    }),
    [view, mode, solver, status, runs, stream, selectedVehicle, setMode, optimize, selectVehicle, reset],
  )

  return <DemoCtx.Provider value={value}>{children}</DemoCtx.Provider>
}
