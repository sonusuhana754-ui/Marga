# MARGA — Frontend

Fleet-routing demo dashboard for SIH 26137. **React + Vite + TypeScript**, MapLibre GL
(keyless Carto dark base), Tailwind v4, Recharts. Plain React state, no router.

Runs entirely on **mock data** until the backend endpoints land — every screen works
offline today.

## Run

```bash
npm install
npm run dev          # http://localhost:5173
```

## What's built

| Screen / feature | Notes |
| --- | --- |
| **Live** — single vehicle | shortest path vs shortest *legal* route for a heavy truck; blocked-edge callout |
| **Live** — fleet | Optimize → per-vehicle routes on real roads; OR-Tools ↔ VA-QPSO toggle redraws the map; click a route → vehicle panel + "why this route" decision weights |
| **Live** — sim clock | play / pause / scrub / speed; vehicle dots interpolate along routes |
| **Live** — volatility | scripted traffic surge; β vs σ² inspector, status pill (stable → threshold crossed → re-optimizing), zone heat-map toggle, traffic congestion on roads |
| **Live** — impact strip | time / fuel / CO₂ / distance, derived from the distance delta + `ASSUMPTIONS` |
| **Benchmark** tab | gap-to-best-known (sorted best-first — OR-Tools wins some instances), convergence curves, results table + CSV |
| **Guided demo** | 7 scripted beats; Next / ← / Esc. Drives the whole UI for a 3-min presentation |

## How it's wired

| Concern | Where |
| --- | --- |
| Map area (bbox, centre, zoom) | `src/config.ts` → `AREA` — **placeholder (Koramangala) until backend locks the sub-graph** |
| API contract types | `src/types/api.ts` — **the backend response models must match this file** |
| Mock fixtures | `src/mocks/` — route geometry is real (OSRM); regenerate with `npm run gen:mocks` |
| Mock ↔ real switch | `VITE_USE_MOCK` (default `true`) + `VITE_API_BASE`; see `.env.example` |
| Impact assumptions | `src/config.ts` → `ASSUMPTIONS` (shown as footnotes in the UI) |
| All shared state | `src/state/DemoProvider.tsx` + `src/state/SimClockProvider.tsx` |

## Endpoints the backend needs (see `src/types/api.ts`)

```
GET  /api/v1/graph              cached road network
POST /api/v1/route              single vehicle — { unconstrained, best, blocked_edges }
POST /api/v1/optimize           fleet VRP — routes[] with timestamps[], decision_weights, cost_vs_next_best
GET  /api/v1/stream/:run_id     volatility / status time-series (frontend consumes it as a series)
POST /api/v1/reoptimize         threshold- or incident-triggered partial re-solve
GET  /api/v1/benchmark          per-solver cost / gap_pct / runtime_ms / convergence
```

Two fields that are easy to forget: **`timestamps[]`** on each route (drives the
animation) and **`zone_volatility[]`** on the stream (drives the β inspector).

## Going live

1. Backend implements the endpoints above to match `src/types/api.ts`.
2. Create `.env.local` with `VITE_USE_MOCK=false` and `VITE_API_BASE=<backend>/api/v1`.
3. Swap `AREA` in `src/config.ts` for the locked sub-graph, update
   `src/mocks/data/points.json`, run `npm run gen:mocks`.

Each API call falls back to its mock on failure, so a backend hiccup during the demo
degrades gracefully rather than blanking the screen.

## Build & deploy

```bash
npm run build        # tsc + vite build → dist/
npm run preview      # serve the build locally
```

Deploy `dist/` to Vercel as a static site (framework preset: **Vite**).
