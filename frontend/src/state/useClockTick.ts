import { useEffect, useState } from 'react'
import { useSimClock } from './simClock'

/** Current sim time + play state, refreshed at ~`fps` for UI display. */
export function useClockTick(fps = 12): { time: number; playing: boolean } {
  const clock = useSimClock()
  const [v, setV] = useState(() => ({ time: clock.getTime(), playing: clock.isPlaying() }))

  useEffect(() => {
    let last = 0
    let lastPlaying = clock.isPlaying()
    return clock.subscribe((time, playing) => {
      const now = performance.now()
      if (playing !== lastPlaying || now - last >= 1000 / fps) {
        last = now
        lastPlaying = playing
        setV({ time, playing })
      }
    })
  }, [clock, fps])

  return v
}
