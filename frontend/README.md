# MARGA — Frontend

Fleet routing dashboard for SIH 26137. React + Vite + TypeScript, MapLibre, Tailwind v4,
Recharts. Runs entirely on mock data until the backend endpoints land.

## Run

```bash
npm install
npm run dev
```

Opens at http://localhost:5173.

## How it's wired

| Concern | Where |
| --- | --- |
| Map area (bbox, centre, zoom) | `src/config.ts` → `AREA` — **placeholder until backend locks the sub-graph** |
| API contract types | `src/types/api.ts` — the backend response models must match this file |
| Mock fixtures | `src/mocks/` (from block 2) |
| Mock ↔ real switch | `VITE_USE_MOCK` env var (default `true`); see `.env.example` |
| Impact assumptions | `src/config.ts` → `ASSUMPTIONS` (shown as footnotes in the UI) |

## Going live

1. Backend implements `GET /graph`, `POST /route`, `POST /optimize`,
   `GET /stream/:run_id` (SSE), `POST /reoptimize`, `GET /benchmark` to match
   `src/types/api.ts`.
2. Set `VITE_USE_MOCK=false` and `VITE_API_BASE` in `.env.local`.
3. Swap the placeholder `AREA` coordinates in `src/config.ts` for the locked
   sub-graph and regenerate mock coordinates.

## Build

```bash
npm run build      # tsc + vite build -> dist/
npm run preview     # serve the build locally
```
