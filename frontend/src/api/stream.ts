import type { StreamTick } from '@/types/api'
import { API_BASE, USE_MOCK } from '@/config'
import { mockStream } from '@/mocks/stream'

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * The volatility / status time-series for a run. The UI consumes it as a
 * timeline synced to the sim clock, so we return the whole series rather than a
 * live push stream. In mock mode it's precomputed; against the real backend we
 * try a series endpoint and fall back to the mock.
 */
export async function getStream(
  runId: string,
  durationSeconds: number,
): Promise<StreamTick[]> {
  if (USE_MOCK) {
    await wait(200)
    return mockStream(durationSeconds)
  }
  try {
    const res = await fetch(`${API_BASE}/stream/${runId}?format=series`)
    if (res.ok) return (await res.json()) as StreamTick[]
  } catch (err) {
    console.warn('[stream] falling back to mock:', err)
  }
  return mockStream(durationSeconds)
}
