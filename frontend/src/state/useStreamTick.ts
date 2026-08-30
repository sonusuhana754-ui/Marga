import { useEffect, useState } from 'react'
import type { StreamTick } from '@/types/api'
import { TICK_SECONDS, tickAt } from '@/mocks/stream'
import { useSimClock } from './simClock'

/** The stream tick for the current sim time. Updates when the tick index changes. */
export function useStreamTick(series: StreamTick[] | null): StreamTick | null {
  const clock = useSimClock()
  const [tick, setTick] = useState<StreamTick | null>(null)

  useEffect(() => {
    if (!series) return
    let lastIdx = -1
    // subscribe fires immediately with the current time, seeding `tick`
    return clock.subscribe((t) => {
      const idx = Math.floor(t / TICK_SECONDS)
      if (idx !== lastIdx) {
        lastIdx = idx
        setTick(tickAt(series, t))
      }
    })
  }, [clock, series])

  return series ? tick : null
}
