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

- There is **no live traffic feed** in this deployment, so the rolling volatility
  window is empty and β sits at βmin. The solver reports
  `solver_diagnostics.volatility_signal: false` instead of inventing a signal.
- OR-Tools reports no per-iteration trace, so its convergence curve is **not
  drawn** and the chart says which solver is missing.
- `smooth_fitness` was measured *worse* (mean 8,500 vs 8,267 over 12 seeds) and
  is off by default; the measurement is recorded in `docs/`.
- The frontend has **no fixture mode**: no mock fallbacks, no synthetic benchmark
  rows, no simulated volatility stream. Failed requests render the error.

## Run it

```bash
# backend (port 8000 by default)
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend (port 5173)
cd frontend
npm install
npm run dev
```

Point the frontend at a non-default backend with `VITE_API_BASE` in
`frontend/.env.local`.

```bash
# tests
cd backend && python3 -m pytest -q     # 156 tests
cd frontend && npm run lint && npm run build
```

Swagger: `http://127.0.0.1:8000/docs`. Health: `GET /health` (reports `degraded`
without Postgres — no endpoint the UI uses touches the database).

## Known gaps

- The OSM sub-graph is not locked: `AREA` in `frontend/src/config.ts` is a
  Koramangala placeholder, and single-vehicle routing needs
  `POST /api/v1/graphs/load` first (the panel offers to trigger it).
- Vehicle height/weight restrictions are modelled in the request schema but not
  in the cost; the single-vehicle `/route` path is the only place they bind.
- No live traffic feed → the adaptive branch of β is exercised only when a
  caller populates `OptimizeService.volatility`.
