import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import type { BenchmarkResponse } from '@/types/api'
import { BENCHMARK_SCENARIOS, RANKABLE_BENCHMARK_SCENARIOS, getBenchmark } from '@/api/benchmark'
import { Segmented } from '@/components/ui/controls'
import { GapChart } from './GapChart'
import { ConvergenceChart } from './ConvergenceChart'
import { ResultsTable } from './ResultsTable'
import { SourceBadge } from './SourceBadge'

const INSTANCE_OPTIONS = BENCHMARK_SCENARIOS.map((id) => ({
  value: id,
  label: RANKABLE_BENCHMARK_SCENARIOS.includes(id) ? id : `${id} ·`,
}))

const DESCRIPTIONS: Record<string, string> = {
  grid_cvrp_25: '25-node grid · 4 vehicles · capacity 9 · 24 stops',
  grid_cvrp_49: '49-node grid · 6 vehicles · capacity 10 · 48 stops',
  grid_vrptw_25: '25-node grid with time windows · 4 vehicles · 24 stops',
  grid_cvrp_8: '8-node grid · 3 vehicles · 7 stops',
  grid_cvrp_6: '6-node grid · 2 vehicles · 5 stops',
  grid_vrptw_8: '8-node grid with time windows · 3 vehicles',
}

/** The small instances cannot rank solvers, and the UI has to say so. */
const TOO_SMALL = new Set(['grid_cvrp_8', 'grid_cvrp_6', 'grid_vrptw_8'])

export function BenchmarkView() {
  const [scenario, setScenario] = useState(BENCHMARK_SCENARIOS[0])
  const [data, setData] = useState<BenchmarkResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const loading = !data || data.scenario_id !== scenario

  useEffect(() => {
    let live = true
    getBenchmark(scenario)
      .then((d) => {
        if (live) {
          setData(d)
          setError(null)
        }
      })
      .catch((e) => {
        if (live) setError(e instanceof Error ? e.message : String(e))
      })
    return () => {
      live = false
    }
  }, [scenario])

  return (
    <div className="absolute inset-0 z-20 overflow-y-auto bg-bg">
      <div className="mx-auto max-w-5xl px-6 pb-16 pt-20">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
          <div>
            <h1 className="font-[Archivo] text-[22px] font-semibold tracking-tight text-ink">
              Benchmark Lab
            </h1>
            <p className="mt-1 max-w-[46ch] text-[13px] text-ink-dim">
              VA-QPSO against the classical baseline on the backend's in-code grid
              scenarios. Each row is measured during the request — where OR-Tools
              wins on cost, it wins here too.
            </p>
          </div>
          <div className="w-[340px]">
            <span className="label-mono">Scenario</span>
            <div className="mt-1.5">
              <Segmented
                size="sm"
                options={INSTANCE_OPTIONS}
                value={scenario}
                onChange={setScenario}
              />
            </div>
          </div>
        </div>

        {loading || !data ? (
          <div className="grid place-items-center py-24 text-ink-mute">
            {error ? (
              <span className="text-[13px] text-red">{error}</span>
            ) : (
              <Loader2 className="h-5 w-5 animate-spin" />
            )}
          </div>
        ) : (
          <>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <SourceBadge source={data.source} />
              <span className="text-[11px] text-ink-mute">
                {DESCRIPTIONS[data.scenario_id] ?? data.scenario_id} · seed {data.scenario_seed} ·
                fleet {Math.round(data.fleet_utilisation * 100)}% loaded
              </span>
              {TOO_SMALL.has(data.scenario_id) && (
                <span className="text-[11px] text-amber">
                  This instance is too small to rank solvers — every arm reaches
                  the optimum, so the tie means nothing.
                </span>
              )}
            </div>

            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              <GapChart results={data.results} />
              <ConvergenceChart results={data.results} />
              <div className="lg:col-span-2">
                <ResultsTable data={data} />
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  )
}