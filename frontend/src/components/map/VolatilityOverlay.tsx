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
        '#1c3b39',
        0.3,
        '#b9822f',
        0.7,
        '#e5654b',
      ],
      'fill-opacity': [
        'interpolate',
        ['linear'],
        ['get', 'sigma'],
        -0.5,
        0,
        0,
        0.04,
        0.35,
        0.2,
        0.85,
        0.36,
      ],
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
        0.05,
        'rgba(255,255,255,0.14)',
        0.6,
        '#e5654b',
      ],
      'line-width': ['interpolate', ['linear'], ['get', 'sigma'], 0.05, 0.8, 0.85, 2.4],
      'line-opacity': [
        'interpolate',
        ['linear'],
        ['get', 'sigma'],
        -0.5,
        0,
        0,
        0.9,
      ],
    },
  },
]

/**
 * Per-zone volatility (σ²) as a heat fill + outline. When hidden, `sigma` is
 * set to a sentinel so both layers fade fully out.
 */
export function VolatilityOverlay({ tick, visible }: { tick: StreamTick | null; visible: boolean }) {
  const data = useMemo(() => {
    const bySigma = new Map((tick?.zone_volatility ?? []).map((z) => [z.zone_id, z.sigma_sq]))
    return {
      type: 'FeatureCollection' as const,
      features: mockGraph.zones.map((z) => ({
        type: 'Feature' as const,
        properties: { sigma: visible ? (bySigma.get(z.zone_id) ?? 0) : -1 },
        geometry: { type: 'Polygon' as const, coordinates: [z.polygon] },
      })),
    }
  }, [tick, visible])

  useSourceLayers('volatility', data, LAYERS, { belowLabels: true })
  return null
}
