# MARGA — Frontend

Fleet-routing demo dashboard for SIH 26137. **React + Vite + TypeScript**, MapLibre GL
(keyless Carto dark base), Tailwind v4, Recharts. Plain React state, no router.

Talks only to the FastAPI backend — **there is no fixture mode**. Every route, cost,
runtime, convergence point and β value on screen is produced by the backend for that
request; if the backend is unreachable the screens show the error instead of numbers.

## Run

```bash
npm install
npm run dev          # http://localhost:5173

# backend must be up (from ../backend):
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API base defaults to `http://localhost:8000/api/v1` (`src/config.ts`). Override it
with `VITE_API_BASE` — put the override in an untracked `.env.local`.

## What's built

| Screen / feature | Notes |
| --- | --- |
| **Live** — anywhere on Earth | Map has no bounding box or zoom lock. Arm "pick a place" and click the map, or type a place name; the backend downloads that area's real OSM road network (`POST /api/v1/graphs/load`) and the view fits itself to it |
| **Live** — single vehicle | `POST /route` on the loaded OSM graph. The area is auto-loaded first; if the download fails the panel prints the backend's own reason |
| **Live** — fleet | Optimize → all three solvers run (`ortools`, `qpso`, `va_qpso`) on depot/stops the backend picked from real junctions; routes are drawn along the returned road geometry, not straight lines |
| **Live** — traffic line | live km/h from `GET /traffic/snapshot`, with its own refresh; `configured: false` and "feed did not answer" are distinct, visible states |
| **Live** — sim clock | play / pause / scrub / speed; vehicle dots interpolate along the measured route timestamps |
| **Live** — β inspector | measured β, one point per iteration, from `solver_diagnostics.beta_history`, plus the probe batch the window was fed (source, time, speeds); states plainly when `volatility_signal: false` (no traffic feed, β at its floor) |
| **Live** — impact strip | only rendered when VA-QPSO actually beats OR-Tools. Distance is a difference of reported leg distances; time, fuel and CO₂ are labelled as modelled from `ASSUMPTIONS` |
| **Benchmark** tab | `POST /api/v1/benchmark` — gap-to-best, convergence (drawn only for solvers that report a trace), results table + CSV, and a "Measured · live backend" badge |
| **Guided demo** | 7 beats; Next / ← / Esc. Captions describe what the backend actually does |

## How it's wired

| Concern | Where |
| --- | --- |
| Map view | `src/config.ts` → `AREA` is the **initial view only** — no bbox, no `maxBounds`, no zoom lock. The area itself is loaded state (`useDemo().area`) |
| Area picker | `src/components/map/AreaPicker.tsx` — click-to-load (`AreaPicker`) and fit-to-bounds (`AreaFramer`) |
| API contract types | `src/types/api.ts` (what the UI renders) and `src/api/backendTypes.ts` (wire format) |
| Wire ↔ UI translation | `src/api/adapter.ts` — the only place the two contracts differ |
| Scene coordinates | `src/scene/` — depot and stop pins only. Scene data, never results |
| Impact assumptions | `src/config.ts` → `ASSUMPTIONS` (always shown as footnotes in the UI) |
| All shared state | `src/state/DemoProvider.tsx` + `src/state/SimClockProvider.tsx` |

## Endpoints consumed

```
POST /api/v1/optimize           fleet VRP — routes[] with geometry[], points[], area{}, traffic{}, convergence[], solver_diagnostics{}
POST /api/v1/route              single vehicle — { unconstrained, best, blocked_edges }
POST /api/v1/graphs/load        OSM graph download by place name or center + dist_m
GET  /api/v1/traffic/snapshot   live per-leg readings for the loaded graph
POST /api/v1/benchmark          per-solver cost / gap_pct / runtime_ms / convergence
GET  /api/v1/benchmark/solvers  solver registry
```

There is **no `/stream` and no `/reoptimize`** in the backend, so the UI has no zone
heat map and no status pills for threshold crossings. Those were removed rather than
simulated: the β inspector plots the solver's own history instead. Traffic arrives the
way it actually exists — one probe batch per solve — and when no API key is configured
the response says `traffic: null` rather than substituting speeds.

## Tests

```bash
npm test             # vitest — adapter contract tests (request/response translation)
```

The adapter tests pin the two things a refactor could silently break: that a loaded
area produces `mode: 'graph'` against the right `graph_key`, and that a response's
road geometry, points, area and traffic reach the UI untouched (with `null` traffic
staying `null`).

## Build & deploy

```bash
npm run build        # tsc + vite build → dist/
npm run preview      # serve the build locally
npm run lint         # oxlint
npm test             # vitest run
```

Deploy `dist/` to Vercel as a static site (framework preset: **Vite**), and point
`VITE_API_BASE` at the running backend.
