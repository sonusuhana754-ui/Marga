import { createContext, useContext } from 'react'

/** Playback speeds, in simulated-seconds per real-second. */
export const SPEEDS = [
  { value: 15, label: 'Slow' },
  { value: 45, label: 'Normal' },
  { value: 120, label: 'Fast' },
] as const

export interface SimClock {
  play(): void
  pause(): void
  toggle(): void
  /** jump to a specific simulated time (seconds), pausing */
  seek(t: number): void
  setSpeed(simSecondsPerRealSecond: number): void
  setDuration(seconds: number): void
  restart(): void

  getTime(): number
  getSpeed(): number
  getDuration(): number
  isPlaying(): boolean

  /** called once per animation frame with the current simulated time */
  subscribe(cb: (time: number, playing: boolean) => void): () => void
}

export const SimClockCtx = createContext<SimClock | null>(null)

export function useSimClock(): SimClock {
  const v = useContext(SimClockCtx)
  if (!v) throw new Error('useSimClock must be used inside <SimClockProvider>')
  return v
}
