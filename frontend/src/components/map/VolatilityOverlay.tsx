import { useMemo } from 'react'
import type { StreamTick } from '@/types/api'
import { mockGraph } from '@/mocks'
import { mulberry32 } from '@/mocks/rng'
import { useSourceLayers } from './useSourceLayers'
import type { LayerDef } from './useSourceLayers'

const LAYERS: LayerDef[] = [
  {
    id: 'volatility-heat',
    type: 'heatmap',
    paint: {
      'heatmap-weight': ['get', 'sigma'],
      'heatmap-intensity': 1.15,
      'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 11, 26, 14, 60, 16, 130],
      'heatmap-color': [
        'interpolate',
        ['linear'],
        ['heatmap-density'],
        0,
        'rgba(0,0,0,0)',
        0.25,
        'rgba(28,59,57,0.35)',
        0.5,
        'rgba(160,120,50,0.5)',
        0.8,
        'rgba(229,101,75,0.62)',
        1,
        'rgba(238,107,77,0.72)',
      ],
      'heatmap-opacity': 0.9,
    },
  },
]

// scatter points per zone so the heat blooms organically, not as a rectangle
function scatterPoints() {
  const rnd = mulberry32(909)
  const out: { zone_id: string; lng: number; lat: number }[] = []
  for (const z of mockGraph.zones) {
    const xs = z.polygon.map((c) => c[0])
    const ys = z.polygon.map((c) => c[1])
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)]
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)]
    for (let i = 0; i < 14; i++) {
      out.push({
        zone_id: z.zone_id,
        lng: x0 + (x1 - x0) * rnd(),
        lat: y0 + (y1 - y0) * rnd(),
      })
    }
  }
  return out
}

const POINTS = scatterPoints()

/** Per-zone volatility (σ²) as an organic heat bloom. */
export function VolatilityOverlay({ tick, visible }: { tick: StreamTick | null; visible: boolean }) {
  const data = useMemo(() => {
    const bySigma = new Map((tick?.zone_volatility ?? []).map((z) => [z.zone_id, z.sigma_sq]))
    return {
      type: 'FeatureCollection' as const,
      features: POINTS.map((p) => ({
        type: 'Feature' as const,
        properties: {
          // small floor so calm zones stay invisible; boost so a real surge reads
          sigma: visible ? Math.max(0, (bySigma.get(p.zone_id) ?? 0) - 0.12) * 1.6 : 0,
        },
        geometry: { type: 'Point' as const, coordinates: [p.lng, p.lat] },
      })),
    }
  }, [tick, visible])

  useSourceLayers('volatility', data, LAYERS, { belowLabels: true })
  return null
}
