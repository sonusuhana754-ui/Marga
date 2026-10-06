/* Vehicle colour ramp — 12 hues chosen to stay distinct on the near-black map
   without vibrating. A vehicle keeps its colour across solvers and modes. */

export const VEHICLE_COLORS = [
  '#2fd9c4', // teal
  '#e8a24a', // amber
  '#6e93e6', // blue
  '#e86f8a', // rose
  '#8ccb5a', // green
  '#b983e0', // violet
  '#49b8d4', // cyan
  '#e0906a', // terracotta
  '#9ad17f', // sage
  '#d46fb8', // magenta
  '#7fa9d9', // steel
  '#c9b45e', // gold
] as const

export function vehicleColor(id: number): string {
  return VEHICLE_COLORS[((id % VEHICLE_COLORS.length) + VEHICLE_COLORS.length) % VEHICLE_COLORS.length]
}

/* Semantic colours, mirrored from the CSS tokens for use in canvas / map / charts. */
export const C = {
  marga: '#2fd9c4',
  margaDeep: '#0f5c55',
  amber: '#e9b23c',
  red: '#ee6b4d',
  green: '#58c98b',
  ink: '#eaf0f1',
  inkDim: '#9aadb0',
  inkMute: '#617376',
  line: '#27353a',
  surface: '#141e21',
  bg: '#090e10',
} as const

/* Congestion overlay colours by level. */
export const congestionColor: Record<'free' | 'moderate' | 'heavy', string> = {
  free: '#3a4a4e',
  moderate: '#e9b23c',
  heavy: '#ee6b4d',
}
