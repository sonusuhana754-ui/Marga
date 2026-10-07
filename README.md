# MARGA — Quantum-Inspired Intelligent Traffic Route Optimization

Fleet routing (CVRP / VRPTW) with a volatility-adaptive quantum-behaved particle
swarm optimizer, benchmarked against OR-Tools on the same instances.

- **Backend** — FastAPI + Python. `backend/`
- **Frontend** — React + Vite + MapLibre. `frontend/`
- **Design doc, review notes, screenshots** — `docs/`

## What is actually implemented

| Algorithm | Where | Status |
| --- | --- | --- |
| OR-Tools (PATH_CHEAPEST_ARC + GUIDED_LOCAL_SEARCH) | `app/algorithms/ortools_solver.py` | baseline |
| QPSO, fixed β | `app/algorithms/qpso_solver.py` (`FixedBetaQPSOSolver`) | ablation anchor |
| VA-QPSO — volatility-adaptive β | `app/algorithms/qpso_solver.py` (`QPSOSolver`) | this project's contribution |

Shared machinery: `qpso.py` (swarm core — φ_ij, mbest, L_ij = 2β|mbest − x_ij|,
logarithmic inverse-CDF sampling, stall limit), `volatility.py` (rolling σ² →
scale-free normalised β = βmin + (βmax − βmin)·Vol(Z)), `random_key.py`
(random-key decode, capacity-bounded split, 2-opt, relocate).

There is no GA / ACO / PSO implementation, and no CVRPLIB integration — the
benchmark runs the in-code grid scenarios registered in `app/algorithms/scenarios.py`.

## Measured, not claimed

Numbers below are from `POST /api/v1/benchmark`, `repeats: 1`, on this machine:

| Scenario | OR-Tools | QPSO | VA-QPSO |
| --- | --- | --- | --- |
| `grid_cvrp_25` | 6,400 (0 %, 2,001 ms) | 8,400 (+31.3 %, 56 ms) | 8,400 (+31.3 %, 85 ms) |
| `grid_cvrp_49` | 13,600 (0 %, ~2,000 ms) | 24,000 (+76 %) | 19,600 (+44 %) |

Read that honestly: **OR-Tools wins on cost on every instance tested.** The QPSO
arms are roughly 20–40× faster per run. VA-QPSO beating the fixed-β anchor is
*preliminary* — it took 2 of 5 seeds on `grid_cvrp_25`, which is not enough to
claim the adaptive β is the reason.

Other facts the UI states rather than hides:

- The traffic feed is **real when configured**: with `TOMTOM_API_KEY` set in
  `backend/.env`, each solve probes the scenario's actual road legs against
  TomTom's live flow feed and feeds the rolling volatility window. With no key
  the response carries `traffic: null` and
  `solver_diagnostics.volatility_signal: false` — β sits at βmin rather than
  being given a signal nobody measured.
- OR-Tools reports no per-iteration trace, so its convergence curve is **not
  drawn** and the chart says which solver is missing.
- `smooth_fitness` was measured *worse* (mean 8,500 vs 8,267 over 12 seeds) and
  is off by default; the measurement is recorded in `docs/`.
- The frontend has **no fixture mode**: no mock fallbacks, no synthetic benchmark
  rows, no simulated volatility stream. Failed requests render the error.

## Run it

```bash
# whole stack in Docker: Postgres + API on 8000 + UI on 3000
docker compose up --build
# open http://localhost:3000 — /api/* is proxied by nginx to the backend,
# so the bundle needs no CORS setup and no hostname baked into it
```

Serving the UI and API from different hosts: build with
`--build-arg VITE_API_BASE=https://api.example.com/api/v1` (baked at build time,
it overrides any `.env` file in the build context).

```bash
# backend (port 8000 by default)
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add TOMTOM_API_KEY for the live traffic feed
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend (port 5173)
cd frontend
npm install
npm run dev
```

The map starts at a placeholder view and is **not locked to it**: arm
"pick a place" and click anywhere, or type a place name, and the backend
downloads that area's OSM road network (`POST /graphs/load`, by name or
`center` + `dist_m`). Every depot, stop and route line then comes from real
junctions and real road paths on that graph. `TOMTOM_API_KEY` is optional —
without it the UI says the feed is not configured.

Point the frontend at a non-default backend with `VITE_API_BASE` in
`frontend/.env.local`.

```bash
# tests
cd backend && pip install -r requirements-dev.txt && python3 -m pytest -q  # 164 tests
cd frontend && npm test && npm run lint && npm run build
```

Swagger: `http://127.0.0.1:8000/docs`. Health: `GET /health` (reports `degraded`
without Postgres — no endpoint the UI uses touches the database).

## Deploy on Vercel

Two projects from this one repository, each with its own Root Directory —
they build independently and talk over HTTPS:

| Project | Root Directory | Detected as |
| --- | --- | --- |
| API | `backend` | FastAPI, entrypoint `app/main.py`, Python 3.12 (`.python-version`), `maxDuration` 300s (`backend/vercel.json`) |
| UI | `frontend` | Vite, output `dist` |

Environment variables (build-time for the UI, runtime for the API):

| Project | Variable | Value |
| --- | --- | --- |
| UI | `VITE_API_BASE` | `https://<api-project>.vercel.app/api/v1` |
| API | `BACKEND_CORS_ORIGINS` | `https://<ui-project>.vercel.app` (comma-separated for more) |
| API | `OSMNX_CACHE_DIR` | `/tmp/marga-cache` |
| API | `GRAPH_CACHE_DIR` | `/tmp/marga-graphs` |
| API | `DEBUG` / `ENVIRONMENT` | `false` / `production` |
| API | `TOMTOM_API_KEY` | optional — live traffic feed, `null` without it |

Stated plainly, because the README does not hide deployment facts either:

- **No Postgres is provisioned on Vercel.** `/api/v1/health` reports
  `degraded`; no endpoint the UI uses touches the database.
- **Filesystem outside `/tmp` is read-only and processes are recycled.**
  `OSMNX_CACHE_DIR` moves the Overpass cache and `GRAPH_CACHE_DIR` persists
  loaded graphs under `/tmp`, so a cold instance rehydrates a graph key
  instead of 404ing. `/tmp` is per-instance: a genuinely fresh instance pays
  one Overpass download per graph.
- **Bundle size is near the limit.** Test dependencies live in
  `requirements-dev.txt`, but the runtime set alone measures **550 MB**
  installed on Linux (ortools 92, pandas 79, pyogrio/GDAL 97, numpy 71).
  Vercel measured the actual function bundle at **414 MB after dependency
  optimization** and the build succeeded. If a build ever fails on size,
  enable Large Functions (5 GB, default on Fluid compute for new projects)
  or fall back to Docker with `docker compose up --build` and point
  `VITE_API_BASE` at that host.

Live deployment from this repository:

- UI: `https://marga-ui.vercel.app`
- API: `https://marga-api.vercel.app`

Git integration is not connected (the Vercel GitHub App is not granted access
to this repository yet), so redeploys run from a checkout:

```bash
(cd backend && vercel --prod --yes)
(cd frontend && vercel --prod --yes --build-env VITE_API_BASE=https://marga-api.vercel.app/api/v1)
```

After changing `BACKEND_CORS_ORIGINS`, redeploy the API project so the new
origins take effect.

## Known gaps

- Vehicle height/weight restrictions are modelled in the request schema but not
  in the cost; the single-vehicle `/route` path is the only place they bind.
- The OSM graph cache is in-memory: restarting the backend forgets loaded
  areas (osmnx's Overpass HTTP cache in `backend/cache/` makes re-downloading
  fast, but a restart still needs one `POST /graphs/load`). Setting
  `GRAPH_CACHE_DIR` persists graphs to disk so a restarted process finds them
  again; it is unset by default.
- VA-QPSO beating the fixed-β anchor is preliminary (2 of 5 seeds on
  `grid_cvrp_25`), and OR-Tools still wins on cost on every instance tested —
  the table above is the measurement, not a marketing number.
