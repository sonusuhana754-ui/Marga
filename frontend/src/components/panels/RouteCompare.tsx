import { Check, X } from 'lucide-react'
import type { RouteResponse, VehicleProfile } from '@/types/api'
import { fmtDuration, fmtKm } from '@/lib/format'

interface RouteCompareProps {
  route: RouteResponse
  profile: VehicleProfile
}

const CLASS_LABEL: Record<VehicleProfile['vehicle_class'], string> = {
  bike: 'Two-wheeler',
  car: 'Car',
  lcv: 'Light commercial',
  heavy_truck: 'Heavy truck',
}

export function RouteCompare({ route, profile }: RouteCompareProps) {
  const { unconstrained, best, blocked_edges } = route
  const block = blocked_edges[0]

  return (
    <div className="panel w-[300px] overflow-hidden">
      <div className="border-b border-line px-4 py-3">
        <div className="label-mono">Single vehicle</div>
        <div className="mt-1 text-[13px] font-medium text-ink">
          {CLASS_LABEL[profile.vehicle_class]} · {profile.height_m} m · {profile.weight_t} t
        </div>
      </div>

      <div className="divide-y divide-line">
        <RouteRow
          tag="Shortest path"
          route={unconstrained}
          tone="reject"
          note={
            block
              ? `Routes under a ${block.limit} m ${block.reason === 'max_height_m' ? 'underpass' : 'limit'}`
              : 'Not legal for this vehicle'
          }
        />
        <RouteRow tag="MARGA route" route={best} tone="accept" note="Clears every restriction" />
      </div>

      <div className="bg-surface-2/40 px-4 py-3 text-[12px] leading-relaxed text-ink-dim">
        The shortest path is{' '}
        <span className="tnum text-ink">
          {fmtKm(best.distance_m - unconstrained.distance_m)}
        </span>{' '}
        closer but sends the truck where it cannot fit. MARGA optimises for the
        lowest-cost <em>feasible</em> route.
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-1.5 border-t border-line px-4 py-3">
        <Key swatch={<span className="h-0.5 w-4 rounded bg-marga" />} label="MARGA route" />
        <Key
          swatch={<span className="h-0.5 w-4 rounded bg-ink-mute [mask-image:repeating-linear-gradient(90deg,#000_0_3px,transparent_3px_6px)]" />}
          label="Shortest"
        />
        <Key swatch={<span className="h-2 w-2 rounded-full border-2 border-amber" />} label="Depot" />
        <Key swatch={<span className="h-2 w-2 rounded-full border-2 border-marga/70" />} label="Stop" />
      </div>
    </div>
  )
}

function RouteRow({
  tag,
  route,
  tone,
  note,
}: {
  tag: string
  route: RouteResponse['best']
  tone: 'accept' | 'reject'
  note: string
}) {
  const ok = tone === 'accept'
  return (
    <div className="px-4 py-3">
      <div className="flex items-center justify-between">
        <span className={`text-[12px] font-semibold ${ok ? 'text-marga' : 'text-ink-dim'}`}>
          {tag}
        </span>
        <span
          className={`flex items-center gap-1 text-[11px] font-medium ${ok ? 'text-green' : 'text-red'}`}
        >
          {ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
          {ok ? 'Legal' : 'Illegal'}
        </span>
      </div>
      <div className="mt-1.5 flex items-baseline gap-3">
        <span className="tnum text-[19px] font-semibold text-ink">{fmtKm(route.distance_m)}</span>
        <span className="tnum text-[13px] text-ink-dim">{fmtDuration(route.eta_s)}</span>
      </div>
      <div className={`mt-0.5 text-[11px] ${ok ? 'text-ink-mute' : 'text-red/80'}`}>{note}</div>
    </div>
  )
}

function Key({ swatch, label }: { swatch: React.ReactNode; label: string }) {
  return (
    <span className="flex items-center gap-1.5 text-[10.5px] text-ink-mute">
      {swatch}
      {label}
    </span>
  )
}
