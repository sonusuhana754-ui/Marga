import type { OptimizeRequest, OptimizeResponse, RouteResponse } from '@/types/api'
import { API_BASE, USE_MOCK } from '@/config'
import { mockOptimize } from '@/mocks/fleet'
import { mockSingleRoute } from '@/mocks'

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** POST /optimize — fleet VRP. Falls back to the mock on any network failure. */
export async function runOptimize(req: OptimizeRequest): Promise<OptimizeResponse> {
  if (USE_MOCK) {
    await wait(900 + Math.random() * 500) // let the "optimizing" state be visible
    return mockOptimize(req.solver)
  }
  try {
    const res = await fetch(`${API_BASE}/optimize`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(req),
    })
    if (!res.ok) throw new Error(`optimize ${res.status}`)
    return (await res.json()) as OptimizeResponse
  } catch (err) {
    console.warn('[optimize] falling back to mock:', err)
    return mockOptimize(req.solver)
  }
}

/** POST /route — single vehicle. Static in mock mode. */
export async function runRoute(): Promise<RouteResponse> {
  if (USE_MOCK) {
    await wait(400)
    return mockSingleRoute
  }
  // real single-vehicle wiring lands with the backend endpoint
  return mockSingleRoute
}
