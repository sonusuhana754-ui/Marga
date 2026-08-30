import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
// CSP build: the web worker is a real file rather than an inline blob, which
// survives strict CSP and locked-down venue machines. Types are shared with the
// main entry (see src/types/maplibre-csp.d.ts).
import maplibregl from 'maplibre-gl/dist/maplibre-gl-csp'
import type { Map as MlMap } from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-csp-worker.js?url'
import { AREA, MAP_STYLE } from '@/config'
import { MapContext } from './context'

maplibregl.setWorkerUrl(workerUrl)

type Phase = 'loading' | 'ready' | 'error'

interface MapCanvasProps {
  children?: ReactNode
}

/**
 * Full-bleed MapLibre canvas. Children mount only once the style is ready and
 * reach the instance through `useMap()`.
 */
export function MapCanvas({ children }: MapCanvasProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MlMap | null>(null)
  const [phase, setPhase] = useState<Phase>('loading')

  useEffect(() => {
    if (!containerRef.current) return

    const instance = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: AREA.center,
      zoom: AREA.zoom,
      minZoom: AREA.minZoom,
      maxZoom: AREA.maxZoom,
      maxBounds: [
        [AREA.bbox[0] - 0.06, AREA.bbox[1] - 0.06],
        [AREA.bbox[2] + 0.06, AREA.bbox[3] + 0.06],
      ],
      attributionControl: false,
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
      renderWorldCopies: false,
    })

    instance.touchZoomRotate.disableRotation()
    instance.addControl(
      new maplibregl.NavigationControl({ showCompass: false, visualizePitch: false }),
      'top-right',
    )

    const onLoad = () => {
      setMap(instance)
      setPhase('ready')
    }
    const onError = (e: { error?: Error }) => {
      const msg = e.error?.message ?? String(e)
      // benign: fired when a layer-scoped listener briefly outlives its layer
      if (msg.includes('cannot be queried for features')) return
      console.warn('[maplibre]', msg)
    }
    // If the style has not loaded within a sensible window, surface it rather
    // than leaving a black rectangle.
    const watchdog = window.setTimeout(() => {
      if (!instance.isStyleLoaded()) setPhase('error')
    }, 12_000)

    instance.on('load', onLoad)
    instance.on('error', onError)

    if (import.meta.env.DEV) {
      ;(window as unknown as { __map?: MlMap }).__map = instance
    }

    return () => {
      window.clearTimeout(watchdog)
      instance.off('load', onLoad)
      instance.off('error', onError)
      instance.remove()
      setMap(null)
    }
  }, [])

  return (
    <div className="absolute inset-0">
      <div ref={containerRef} className="h-full w-full" />

      {/* Depth vignette — decoration only, never intercepts the map. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'radial-gradient(120% 80% at 50% 0%, transparent 55%, rgba(0,0,0,0.28) 100%)',
        }}
      />

      {phase === 'loading' && (
        <div className="pointer-events-none absolute inset-0 grid place-items-center">
          <span className="label-mono animate-pulse">loading map…</span>
        </div>
      )}

      {phase === 'error' && (
        <div className="absolute inset-0 grid place-items-center bg-bg/60">
          <div className="panel max-w-sm p-5 text-center">
            <p className="text-sm text-ink">Base map didn’t load.</p>
            <p className="mt-1.5 text-xs text-ink-dim">
              The tile server may be unreachable on this network. Routes and data
              still work — reload to retry the map.
            </p>
          </div>
        </div>
      )}

      {map && <MapContext.Provider value={map}>{children}</MapContext.Provider>}
    </div>
  )
}
