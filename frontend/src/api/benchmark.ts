import type { BenchmarkResponse } from '@/types/api'
import { API_BASE, USE_MOCK } from '@/config'
import { mockBenchmark } from '@/mocks/benchmark'

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** GET /benchmark?instance=… — falls back to the mock on any failure. */
export async function getBenchmark(instance: string): Promise<BenchmarkResponse> {
  if (USE_MOCK) {
    await wait(350)
    return mockBenchmark(instance)
  }
  try {
    const res = await fetch(`${API_BASE}/benchmark?instance=${encodeURIComponent(instance)}`)
    if (res.ok) return (await res.json()) as BenchmarkResponse
  } catch (err) {
    console.warn('[benchmark] falling back to mock:', err)
  }
  return mockBenchmark(instance)
}
