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

type Phase = 'loading' | 'ready' | 'slow'

interface MapCanvasProps {
  children?: ReactNode
}

/**
 * Full-bleed MapLibre canvas. Children mount once the style is ready. A slow
 * tile provider never blocks the view — it just shows a small note while the
 * map keeps loading in the background.
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

    // As soon as the style spec is usable, hand the map to the context so our
    // layers mount and render progressively while tiles stream in.
    const tryMountContext = () => {
      if (instance.isStyleLoaded()) {
        setMap((m) => m ?? instance)
        setPhase('ready')
      }
    }
    instance.on('styledata', tryMountContext)
    instance.on('load', tryMountContext)

    const onError = (e: { error?: Error }) => {
      const msg = e.error?.message ?? String(e)
      if (msg.includes('cannot be queried for features')) return
      console.warn('[maplibre]', msg)
    }
    instance.on('error', onError)

    const watchdog = window.setTimeout(() => {
      setPhase((p) => (p === 'ready' ? p : 'slow'))
    }, 15_000)

    if (import.meta.env.DEV) {
      ;(window as unknown as { __map?: MlMap }).__map = instance
    }

    return () => {
      window.clearTimeout(watchdog)
      instance.off('styledata', tryMountContext)
      instance.off('load', tryMountContext)
      instance.off('error', onError)
      instance.remove()
      setMap(null)
    }
  }, [])

  return (
    <div className="absolute inset-0">
      <div ref={containerRef} className="h-full w-full" />

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

      {phase === 'slow' && (
        <div className="pointer-events-none absolute bottom-28 left-1/2 -translate-x-1/2">
          <span className="panel px-3 py-1.5 text-[11px] text-ink-dim">
            base map loading slowly — routes and data still work
          </span>
        </div>
      )}

      {map && <MapContext.Provider value={map}>{children}</MapContext.Provider>}
    </div>
  )
}
