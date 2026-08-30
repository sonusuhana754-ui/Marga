/**
 * Mock fixtures. These match src/types/api.ts exactly and stand in for the
 * backend until the real endpoints land. When VITE_USE_MOCK is false the api
 * layer talks to the backend instead and none of this is used.
 */
export { mockGraph, zoneAt } from './graph'
export { DEPOT, STOPS, mockSingleRoute, mockImpactSample } from './scenario'
export { mockOptimize } from './fleet'
