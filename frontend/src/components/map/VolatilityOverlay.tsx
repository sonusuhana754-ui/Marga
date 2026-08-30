import { useMemo } from 'react'
import type { StreamTick } from '@/types/api'
import { mockGraph } from '@/mocks'
import { useSourceLayers } from './useSourceLayers'
import type { LayerDef } from './useSourceLayers'

const LAYERS: LayerDef[] = [
  {
    id: 'volatility-fill',
    type: 'fill',
    paint: {
      'fill-color': [
        'interpolate',
        ['linear'],
        ['get', 'sigma'],
        0,
        '#0f5c55',
        0.35,
        '#e9b23c',
        0.75,
        '#ee6b4d',
      ],
      'fill-opacity': ['interpolate', ['linear'], ['get', 'sigma'], 0, 0, 0.15, 0.06, 0.85, 0.32],
    },
  },
  {
    id: 'volatility-line',
    type: 'line',
    paint: {
      'line-color': [
        'interpolate',
        ['linear'],
        ['get', 'sigma'],
        0.15,
        'rgba(255,255,255,0.06)',
        0.85,
        '#ee6b4d',
      ],
      'line-width': ['interpolate', ['linear'], ['get', 'sigma'], 0.3, 0.5, 0.85, 1.5],
    },
  },
]

/** Per-zone volatility (σ²) as a heat fill. Reads the current stream tick. */
export function VolatilityOverlay({ tick, visible }: { tick: StreamTick | null; visible: boolean }) {
  const data = useMemo(() => {
    const bySigma = new Map(
      (tick?.zone_volatility ?? []).map((z) => [z.zone_id, z.sigma_sq]),
    )
    return {
      type: 'FeatureCollection' as const,
      features: mockGraph.zones.map((z) => ({
        type: 'Feature' as const,
        properties: { sigma: visible ? (bySigma.get(z.zone_id) ?? 0) : 0 },
        geometry: { type: 'Polygon' as const, coordinates: [z.polygon] },
      })),
    }
  }, [tick, visible])

  useSourceLayers('volatility', data, LAYERS, { belowLabels: true })
  return null
}
