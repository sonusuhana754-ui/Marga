import { Clock, Droplet, Leaf, Route } from 'lucide-react'
import type { ImpactFigures } from '@/types/api'
import { fmtDuration, fmtKg, fmtKm, fmtLitres } from '@/lib/format'
import { ASSUMPTIONS } from '@/config'

interface ImpactStripProps {
  impact: ImpactFigures
  /** solver these savings are measured against */
  baseline?: string
}

export function ImpactStrip({ impact, baseline = 'OR-Tools' }: ImpactStripProps) {
  const tiles = [
    {
      icon: Clock,
      label: 'Travel time saved',
      value: fmtDuration(impact.time_saved_s),
      foot: `vs ${baseline}`,
    },
    {
      icon: Droplet,
      label: 'Fuel saved',
      value: fmtLitres(impact.fuel_saved_l),
      foot: `${ASSUMPTIONS.fuelPerKm} L/km`,
    },
    {
      icon: Leaf,
      label: 'CO₂ avoided',
      value: fmtKg(impact.co2_saved_kg),
      foot: `${ASSUMPTIONS.co2PerLitre} kg/L diesel`,
    },
    {
      icon: Route,
      label: 'Distance reduced',
      value: fmtKm(impact.distance_saved_m),
      foot: `vs ${baseline}`,
    },
  ]

  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between gap-6 border-b border-line px-4 py-2">
        <span className="label-mono">Scenario impact · vs {baseline}</span>
        <span className="text-[10px] font-medium text-amber">
          {impact.measured ? 'measured' : 'mock · not yet measured'}
        </span>
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4">
        {tiles.map((t) => (
          <div key={t.label} className="border-line px-4 py-3 [&:not(:last-child)]:border-r">
            <div className="flex items-center gap-1.5 text-ink-mute">
              <t.icon className="h-3.5 w-3.5" />
              <span className="text-[10.5px] font-medium uppercase tracking-wide">{t.label}</span>
            </div>
            <div className="tnum mt-1.5 text-[22px] font-semibold text-ink">{t.value}</div>
            <div className="text-[10px] text-ink-mute">{t.foot}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
