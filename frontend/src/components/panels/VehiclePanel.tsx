import { X } from 'lucide-react'
import type { FleetRoute, VehicleProfile } from '@/types/api'
import { fmtDuration, fmtKm } from '@/lib/format'
import { vehicleColor } from '@/lib/palette'

interface VehiclePanelProps {
  route: FleetRoute
  profile: VehicleProfile
  onClose: () => void
}

export function VehiclePanel({ route, profile, onClose }: VehiclePanelProps) {
  const eta = route.timestamps.at(-1) ?? 0
  const stops = Math.max(0, route.stop_sequence.length - 2) // minus depot at both ends

  return (
    <div className="panel w-full overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ background: vehicleColor(route.vehicle_id) }}
          />
          <span className="text-[13px] font-semibold text-ink">
            Vehicle {String(route.vehicle_id + 1).padStart(2, '0')}
          </span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="text-ink-mute transition-colors hover:text-ink"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <dl className="divide-y divide-line text-[12px]">
        <Row label="Type">Heavy delivery truck</Row>
        <Row label="Load">
          <span className="tnum">{route.load} / 100</span>
        </Row>
        <Row label="Dimensions">
          <span className="tnum">
            {profile.length_m} m · {profile.height_m} m · {profile.weight_t} t
          </span>
        </Row>
        <Row label="Restrictions">
          {route.restrictions_applied > 0 ? (
            <span className="text-amber">
              applied — {route.restrictions_applied} edge
              {route.restrictions_applied > 1 ? 's' : ''} avoided
            </span>
          ) : (
            <span className="text-ink-mute">none on this route</span>
          )}
        </Row>
        <Row label="Stops">
          <span className="tnum">{stops}</span>
        </Row>
        <Row label="Route">
          <span className="tnum">
            {fmtKm(route.distance_m)} · {fmtDuration(eta)}
          </span>
        </Row>
      </dl>
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 py-2.5">
      <dt className="text-ink-mute">{label}</dt>
      <dd className="font-medium text-ink">{children}</dd>
    </div>
  )
}
