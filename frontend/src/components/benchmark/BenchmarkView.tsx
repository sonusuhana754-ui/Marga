import { useEffect, useState } from 'react'
import { Loader2 } from 'lucide-react'
import type { BenchmarkResponse } from '@/types/api'
import { getBenchmark } from '@/api/benchmark'
import { BENCHMARK_INSTANCES } from '@/mocks/benchmark'
import { Segmented } from '@/components/ui/controls'
import { GapChart } from './GapChart'
import { ConvergenceChart } from './ConvergenceChart'
import { ResultsTable } from './ResultsTable'

const INSTANCE_OPTIONS = BENCHMARK_INSTANCES.map((id) => ({
  value: id,
  label: id === 'bengaluru-live' ? 'Bengaluru (live)' : id,
}))

export function BenchmarkView() {
  const [instance, setInstance] = useState(BENCHMARK_INSTANCES[0])
  const [data, setData] = useState<BenchmarkResponse | null>(null)
  const loading = !data || data.instance !== instance

  useEffect(() => {
    let live = true
    getBenchmark(instance).then((d) => {
      if (live) setData(d)
    })
    return () => {
      live = false
    }
  }, [instance])

  return (
    <div className="absolute inset-0 z-20 overflow-y-auto bg-bg">
      <div className="mx-auto max-w-5xl px-6 pb-16 pt-20">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-line pb-4">
          <div>
            <h1 className="font-[Archivo] text-[22px] font-semibold tracking-tight text-ink">
              Benchmark Lab
            </h1>
            <p className="mt-1 text-[13px] text-ink-dim">
              VA-QPSO against classical baselines on standard instances and the
              live scenario. Results shown as measured — where OR-Tools wins, it
              wins.
            </p>
          </div>
          <div className="w-[320px]">
            <span className="label-mono">Instance</span>
            <div className="mt-1.5">
              <Segmented
                size="sm"
                options={INSTANCE_OPTIONS}
                value={instance}
                onChange={setInstance}
              />
            </div>
          </div>
        </div>

        {loading || !data ? (
          <div className="grid place-items-center py-24 text-ink-mute">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : (
          <div className="mt-6 grid gap-4 lg:grid-cols-2">
            <GapChart results={data.results} />
            <ConvergenceChart results={data.results} />
            <div className="lg:col-span-2">
              <ResultsTable data={data} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
