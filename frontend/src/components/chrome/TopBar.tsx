import { Play } from 'lucide-react'
import { AREA } from '@/config'
import { useDemo } from '@/state/demoStore'
import type { View } from '@/state/demoStore'
import { Segmented } from '@/components/ui/controls'

function MargaMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} fill="none" aria-hidden>
      <path
        d="M7 24C12 24 12 9 17.5 9C22 9 22 15 26 9"
        stroke="var(--color-marga)"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      <circle cx="7" cy="24" r="3.2" fill="var(--color-marga)" />
      <circle cx="26" cy="9" r="3.2" fill="var(--color-amber)" />
    </svg>
  )
}

const VIEW_OPTIONS: { value: View; label: string }[] = [
  { value: 'live', label: 'Live' },
  { value: 'benchmark', label: 'Benchmark' },
]

export function TopBar() {
  const { view, setView, guided, setGuided } = useDemo()

  return (
    <header className="pointer-events-none absolute inset-x-0 top-0 z-30 flex items-start justify-between p-4">
      <div className="pointer-events-auto flex items-center gap-2.5">
        <div className="panel flex items-center gap-3 px-3.5 py-2.5">
          <MargaMark className="h-7 w-7" />
          <div className="leading-none">
            <div className="flex items-baseline gap-2">
              <span className="text-[15px] font-semibold tracking-[0.06em] text-ink">MARGA</span>
              <span className="text-[12px] font-medium text-ink-mute">Fleet Routing</span>
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <span
                className={`inline-block h-1.5 w-1.5 rounded-full ${
                  AREA.locked ? 'bg-green' : 'bg-amber'
                }`}
              />
              <span className="label-mono !text-[9.5px] !tracking-[0.12em] !text-ink-dim">
                {AREA.label}
                {!AREA.locked && ' · area not locked'}
              </span>
            </div>
          </div>
        </div>

        <div className="panel w-[184px] p-1">
          <Segmented<View> size="sm" options={VIEW_OPTIONS} value={view} onChange={setView} />
        </div>
      </div>

      <button
        type="button"
        onClick={() => setGuided(!guided)}
        className={`panel pointer-events-auto flex items-center gap-2 px-3.5 py-2.5 text-[13px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-marga ${
          guided ? 'text-marga' : 'text-ink hover:text-marga'
        }`}
      >
        <Play className="h-3.5 w-3.5" fill="currentColor" />
        Guided demo
      </button>
    </header>
  )
}
