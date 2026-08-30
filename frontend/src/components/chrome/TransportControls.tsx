import { useState } from 'react'
import { Pause, Play, RotateCcw } from 'lucide-react'
import { useSimClock } from '@/state/simClock'
import { SPEEDS } from '@/state/simClock'
import { useClockTick } from '@/state/useClockTick'
import { fmtClock } from '@/lib/format'
import { Segmented } from '@/components/ui/controls'

export function TransportControls() {
  const clock = useSimClock()
  const { time, playing } = useClockTick()
  const [speed, setSpeedState] = useState(() => clock.getSpeed())
  const duration = clock.getDuration()

  const changeSpeed = (v: string) => {
    const n = Number(v)
    setSpeedState(n)
    clock.setSpeed(n)
  }

  return (
    <div className="panel flex items-center gap-3 px-3 py-2.5">
      <button
        type="button"
        onClick={() => clock.toggle()}
        className="grid h-8 w-8 place-items-center rounded-full bg-marga text-[#04211e] transition-transform hover:scale-105"
        aria-label={playing ? 'Pause' : 'Play'}
      >
        {playing ? (
          <Pause className="h-3.5 w-3.5" fill="currentColor" />
        ) : (
          <Play className="ml-0.5 h-3.5 w-3.5" fill="currentColor" />
        )}
      </button>

      <button
        type="button"
        onClick={() => clock.seek(0)}
        className="text-ink-mute transition-colors hover:text-ink"
        aria-label="Restart"
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </button>

      <input
        type="range"
        min={0}
        max={Math.max(duration, 1)}
        step={1}
        value={time}
        onChange={(e) => clock.seek(Number(e.target.value))}
        className="h-1 w-40 cursor-pointer appearance-none rounded-full bg-line accent-marga"
        aria-label="Scrub timeline"
      />

      <span className="tnum whitespace-nowrap text-[11px] text-ink-dim">
        {fmtClock(time)} <span className="text-ink-mute">/ {fmtClock(duration)}</span>
      </span>

      <Segmented
        size="sm"
        options={SPEEDS.map((s) => ({ value: String(s.value), label: s.label }))}
        value={String(speed)}
        onChange={changeSpeed}
      />
    </div>
  )
}
