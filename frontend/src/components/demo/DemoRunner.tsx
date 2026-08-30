import { useCallback, useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Loader2, X } from 'lucide-react'
import { useDemo } from '@/state/demoStore'
import { useSimClock } from '@/state/simClock'
import type { DemoValue } from '@/state/demoStore'
import type { SimClock } from '@/state/simClock'

interface Beat {
  title: string
  caption: string
  apply: (demo: DemoValue, clock: SimClock) => void | Promise<void>
}

const BEATS: Beat[] = [
  {
    title: 'The network',
    caption:
      'A real Bengaluru road network — a depot, delivery stops, and one heavy truck. Everything runs on the actual OSM street graph.',
    apply: (d) => {
      d.setView('live')
      d.setMode('single')
      d.selectVehicle(null)
    },
  },
  {
    title: 'Vehicle constraints',
    caption:
      'The shortest path sends the 4.1 m truck under a 4.5 m underpass. MARGA returns the shortest route that is actually legal for this vehicle.',
    apply: (d) => {
      d.setMode('single')
    },
  },
  {
    title: 'The fleet problem',
    caption:
      '20 stops, 2 trucks. Which truck serves which stops, in what order — the NP-hard part that exact solvers cannot scale to.',
    apply: async (d) => {
      d.setMode('fleet')
      d.selectVehicle(null)
      if (d.status !== 'ready') await d.optimize()
    },
  },
  {
    title: 'Benchmarked',
    caption:
      'Against OR-Tools on this scenario: VA-QPSO finds a lower-cost plan, OR-Tools is quicker. The Benchmark tab shows the instances where OR-Tools wins.',
    apply: (d, c) => {
      d.setSolver('va_qpso')
      c.seek(0)
    },
  },
  {
    title: 'Adapting to traffic',
    caption:
      'Background traffic surges in one zone. MARGA holds the routes steady through minor change, then re-optimizes only the affected zone.',
    apply: (_d, c) => {
      c.seek(360)
      c.play()
    },
  },
  {
    title: 'β responds',
    caption:
      'β and σ² come straight from the solver, one value per zone per tick. Here they climb together as that zone congests.',
    apply: (_d, c) => {
      c.seek(520)
      c.pause()
    },
  },
  {
    title: 'Why, and what it saved',
    caption:
      'The decision weights behind the chosen route — and the measured impact: travel time, fuel, CO₂.',
    apply: (d, c) => {
      c.pause()
      d.selectVehicle(0)
    },
  },
]

export function DemoRunner() {
  const demo = useDemo()
  const clock = useSimClock()
  const [beat, setBeat] = useState(0)
  const demoRef = useRef(demo)
  // the only beat that awaits is #3 (it may run optimize)
  const busy = demo.status === 'optimizing'

  useEffect(() => {
    demoRef.current = demo
  })

  // run the current beat whenever it changes
  useEffect(() => {
    void BEATS[beat].apply(demoRef.current, clock)
  }, [beat, clock])

  const exit = useCallback(() => {
    clock.pause()
    demoRef.current.setGuided(false)
  }, [clock])

  const next = useCallback(() => setBeat((b) => Math.min(BEATS.length - 1, b + 1)), [])
  const prev = useCallback(() => setBeat((b) => Math.max(0, b - 1)), [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === ' ') {
        e.preventDefault()
        next()
      } else if (e.key === 'ArrowLeft') {
        prev()
      } else if (e.key === 'Escape') {
        exit()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [next, prev, exit])

  const b = BEATS[beat]
  const last = beat === BEATS.length - 1

  return (
    <div className="pointer-events-none absolute inset-x-0 top-4 z-40 flex justify-center px-4">
      <div className="panel pointer-events-auto w-[min(640px,100%)] overflow-hidden">
        <div className="flex items-center justify-between border-b border-line px-4 py-2">
          <span className="label-mono !text-marga">
            Guided demo · {beat + 1} / {BEATS.length}
          </span>
          <span className="text-[11px] font-medium text-ink-dim">{b.title}</span>
        </div>

        <p className="px-4 py-3 text-[13.5px] leading-relaxed text-ink">{b.caption}</p>

        <div className="flex items-center gap-2 border-t border-line px-3 py-2.5">
          <button
            type="button"
            onClick={prev}
            disabled={beat === 0 || busy}
            className="grid h-7 w-7 place-items-center rounded-md border border-line text-ink-dim transition-colors hover:text-ink disabled:opacity-30"
            aria-label="Previous"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={exit}
            className="rounded-md px-2.5 py-1 text-[11px] font-medium text-ink-mute transition-colors hover:text-ink"
          >
            <X className="mr-1 inline h-3 w-3" />
            Exit
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={last ? exit : next}
            disabled={busy}
            className="flex items-center gap-1.5 rounded-md bg-marga px-3 py-1.5 text-[12px] font-semibold text-[#04211e] transition-transform hover:scale-[1.02] disabled:opacity-60"
          >
            {busy ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : last ? (
              'Done'
            ) : (
              <>
                Next
                <ArrowRight className="h-3.5 w-3.5" />
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
