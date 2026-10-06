import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { SimClockCtx, SPEEDS } from './simClock'
import type { SimClock } from './simClock'

type Internal = SimClock & { start(): void; stop(): void }

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(v, hi))

function createClock(): Internal {
  const state = { time: 0, playing: false, speed: SPEEDS[1].value as number, duration: 0 }
  // playback is anchored to wall-clock time so it stays correct even when the
  // tab is hidden and rAF/interval are throttled.
  let anchorReal = 0
  let anchorTime = 0

  const subs = new Set<(t: number, playing: boolean) => void>()
  const emit = () => {
    for (const cb of subs) cb(state.time, state.playing)
  }

  const recompute = () => {
    if (!state.playing) return
    const elapsed = ((performance.now() - anchorReal) / 1000) * state.speed
    state.time = anchorTime + elapsed
    if (state.time >= state.duration) {
      state.time = state.duration
      state.playing = false
    }
  }

  const anchor = () => {
    anchorTime = state.time
    anchorReal = performance.now()
  }

  let intervalId = 0
  let raf = 0

  const onHide = () => {
    if (document.hidden && state.playing) {
      recompute()
      state.playing = false
      emit()
    }
  }

  const clock: Internal = {
    play() {
      if (state.duration === 0) return
      if (state.time >= state.duration) state.time = 0
      state.playing = true
      anchor()
      emit()
    },
    pause() {
      recompute()
      state.playing = false
      emit()
    },
    toggle() {
      if (state.playing) clock.pause()
      else clock.play()
    },
    seek(t) {
      recompute()
      state.time = clamp(t, 0, state.duration)
      state.playing = false
      anchor()
      emit()
    },
    setSpeed(s) {
      recompute()
      state.speed = s
      anchor()
    },
    setDuration(d) {
      state.duration = Math.max(0, d)
      if (state.time > state.duration) state.time = state.duration
      anchor()
      emit()
    },
    restart() {
      state.time = 0
      anchor()
      state.playing = state.duration > 0
      emit()
    },
    getTime: () => state.time,
    getSpeed: () => state.speed,
    getDuration: () => state.duration,
    isPlaying: () => state.playing,
    subscribe(cb) {
      subs.add(cb)
      cb(state.time, state.playing)
      return () => {
        subs.delete(cb)
      }
    },
    start() {
      intervalId = window.setInterval(() => {
        if (state.playing) {
          recompute()
          emit()
        }
      }, 40)
      // rAF adds 60fps smoothness while the tab is visible
      const frame = () => {
        if (state.playing) {
          recompute()
          emit()
        }
        raf = requestAnimationFrame(frame)
      }
      raf = requestAnimationFrame(frame)
      // pause if the presenter switches away — don't silently jump ahead
      document.addEventListener('visibilitychange', onHide)
    },
    stop() {
      window.clearInterval(intervalId)
      cancelAnimationFrame(raf)
      document.removeEventListener('visibilitychange', onHide)
    },
  }

  return clock
}

/**
 * A single clock driving simulated time. Subscribers are called on every
 * change; the clock object identity never changes, so consuming it never causes
 * a React re-render. UI that displays time subscribes and throttles its own
 * setState (see useClockTick).
 */
export function SimClockProvider({ children }: { children: ReactNode }) {
  const [clock] = useState(createClock)

  useEffect(() => {
    clock.start()
    return () => clock.stop()
  }, [clock])

  return <SimClockCtx.Provider value={clock}>{children}</SimClockCtx.Provider>
}
