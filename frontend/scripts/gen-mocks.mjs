/**
 * Generate mock route geometry that follows real roads.
 *
 *   npm run gen:mocks
 *
 * Reads src/mocks/data/points.json (hand-authored anchor points), asks the
 * public OSRM demo server for driving routes between them, and writes:
 *   src/mocks/data/single-route.json   RouteResponse  (car vs truck-feasible)
 *   src/mocks/data/fleet-routes.json   FleetRoute[]   (depot -> stops -> depot)
 *
 * Run this again after moving the anchor points (e.g. once the backend locks
 * the real sub-graph). Needs network access; the output is committed so the
 * app itself never calls OSRM.
 */
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const DIR = path.dirname(fileURLToPath(import.meta.url))
const DATA = path.join(DIR, '..', 'src', 'mocks', 'data')
const OSRM = 'https://router.project-osrm.org/route/v1/driving'

const points = JSON.parse(fs.readFileSync(path.join(DATA, 'points.json'), 'utf8'))

const toPair = (c) => `${c[0]},${c[1]}`
const R = 6371000
const rad = (d) => (d * Math.PI) / 180
function haversine(a, b) {
  const dLat = rad(b[1] - a[1])
  const dLng = rad(b[0] - a[0])
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(h))
}
const pathLength = (p) => p.reduce((t, c, i) => (i ? t + haversine(p[i - 1], c) : 0), 0)

async function route(coords, extra = '') {
  const url = `${OSRM}/${coords.map(toPair).join(';')}?overview=full&geometries=geojson${extra}`
  const res = await fetch(url)
  if (!res.ok) throw new Error(`OSRM ${res.status} for ${url}`)
  const json = await res.json()
  if (json.code !== 'Ok') throw new Error(`OSRM ${json.code}`)
  return json.routes[0]
}

/** Per-vertex timestamps (seconds) proportional to segment length. */
function timestamps(pathCoords, totalSeconds) {
  const cum = [0]
  for (let i = 1; i < pathCoords.length; i++) {
    cum.push(cum[i - 1] + haversine(pathCoords[i - 1], pathCoords[i]))
  }
  const total = cum[cum.length - 1] || 1
  return cum.map((d) => Math.round((d / total) * totalSeconds))
}

/** Point ~40% along the car route that is well clear of the truck route. */
function underpassSegment(carPath, truckPath) {
  const idx = Math.floor(carPath.length * 0.4)
  for (let i = idx; i < carPath.length - 1; i++) {
    const p = carPath[i]
    const near = truckPath.some((q) => haversine(p, q) < 160)
    if (!near) return [carPath[i], carPath[i + 1]]
  }
  return [carPath[idx], carPath[idx + 1]]
}

async function main() {
  const { depot, destination, truck_via, stops } = points

  console.log('routing single-vehicle car + truck…')
  const car = await route([depot, destination])
  const truck = await route([depot, truck_via, destination], '&continue_straight=false')

  const carPath = car.geometry.coordinates
  const truckPath = truck.geometry.coordinates
  const block = underpassSegment(carPath, truckPath)

  const singleRoute = {
    unconstrained: {
      path: carPath,
      distance_m: Math.round(car.distance),
      eta_s: Math.round(car.duration * 1.7), // demo traffic multiplier on the congested corridor
      feasible_for_profile: false,
    },
    best: {
      path: truckPath,
      distance_m: Math.round(truck.distance),
      eta_s: Math.round(truck.duration * 1.15),
      feasible_for_profile: true,
    },
    blocked_edges: [
      { edge_id: 'e_underpass_1', geometry: block, reason: 'max_height_m', limit: 4.5 },
    ],
    method: 'dijkstra',
  }
  fs.writeFileSync(
    path.join(DATA, 'single-route.json'),
    JSON.stringify(singleRoute, null, 2) + '\n',
  )
  console.log(
    `  car ${(car.distance / 1000).toFixed(2)} km · truck ${(truck.distance / 1000).toFixed(2)} km`,
  )

  console.log('routing fleet (nearest-neighbour tour)…')
  const nnOrder = (start) => {
    const remaining = [...stops]
    const order = []
    let cursor = start
    while (remaining.length) {
      let bi = 0
      let bd = Infinity
      remaining.forEach((s, i) => {
        const d = haversine(cursor, s)
        if (d < bd) {
          bd = d
          bi = i
        }
      })
      order.push(remaining[bi])
      cursor = remaining[bi]
      remaining.splice(bi, 1)
    }
    return order
  }

  async function buildFleet(order, { runtimeMul, restrictionsOnV0 }) {
    const half = Math.ceil(order.length / 2)
    const legs = [
      [depot, ...order.slice(0, half), depot],
      [depot, ...order.slice(half), depot],
    ]
    const fleet = []
    for (let v = 0; v < legs.length; v++) {
      const r = await route(legs[v])
      const p = r.geometry.coordinates
      const dur = Math.round(r.duration * runtimeMul)
      fleet.push({
        vehicle_id: v,
        stop_sequence: legs[v].map((_, i) => i),
        path: p,
        timestamps: timestamps(p, dur),
        load: 60 + v * 17,
        distance_m: Math.round(r.distance),
        restrictions_applied: v === 0 && restrictionsOnV0 ? 2 : 0,
        decision_weights: {
          traffic: 0.42,
          distance: 0.31,
          congestion: 0.18,
          constraints: 0.09,
        },
        cost_vs_next_best: [Math.round(r.distance), Math.round(r.distance * 1.06)],
      })
    }
    return fleet
  }

  const nn = nnOrder(depot)
  // VA-QPSO: nearest-neighbour tour, tighter timing
  const fleetOurs = await buildFleet(nn, { runtimeMul: 1.25, restrictionsOnV0: true })
  // OR-Tools: a slightly different split (rotate the order) so the map visibly
  // changes on solver toggle
  const rotated = [...nn.slice(2), ...nn.slice(0, 2)]
  const fleetBaseline = await buildFleet(rotated, { runtimeMul: 1.32, restrictionsOnV0: false })

  fs.writeFileSync(
    path.join(DATA, 'fleet-va_qpso.json'),
    JSON.stringify(fleetOurs, null, 2) + '\n',
  )
  fs.writeFileSync(
    path.join(DATA, 'fleet-ortools.json'),
    JSON.stringify(fleetBaseline, null, 2) + '\n',
  )
  console.log(
    `  va_qpso ${fleetOurs.reduce((s, f) => s + f.distance_m, 0)} m · ` +
      `ortools ${fleetBaseline.reduce((s, f) => s + f.distance_m, 0)} m`,
  )

  void pathLength
  console.log('done.')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
