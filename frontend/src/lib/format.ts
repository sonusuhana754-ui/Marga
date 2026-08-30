/* Display formatting. Keep every number the same across the UI. */

/** 190 -> "3 min", 4500 -> "1 h 15 m", 45 -> "45 s" */
export function fmtDuration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  if (s < 60) return `${s} s`
  const m = Math.round(s / 60)
  if (m < 60) return `${m} min`
  const h = Math.floor(m / 60)
  const rem = m % 60
  return rem ? `${h} h ${rem} m` : `${h} h`
}

/** 14320 -> "14.3 km" */
export function fmtKm(metres: number): string {
  return `${(metres / 1000).toFixed(1)} km`
}

/** 18422.5 -> "18,423" (Indian grouping) */
export function fmtInt(n: number): string {
  return Math.round(n).toLocaleString('en-IN')
}

/** 0.412 -> "0.412" */
export function fmtFixed(n: number, digits = 2): string {
  return n.toFixed(digits)
}

export function fmtLitres(l: number): string {
  return `${l.toFixed(1)} L`
}

export function fmtKg(kg: number): string {
  return `${kg.toFixed(1)} kg`
}

/** 0.045 -> "4.5%" */
export function fmtPct(fraction: number, digits = 1): string {
  return `${(fraction * 100).toFixed(digits)}%`
}

/** 2140 -> "2.14 s", 410 -> "0.41 s" */
export function fmtSeconds(ms: number): string {
  return `${(ms / 1000).toFixed(2)} s`
}

/** currency, Indian grouping, no decimals: 4218 -> "₹4,218" */
export function fmtMoney(amount: number, symbol = '₹'): string {
  return `${symbol}${Math.round(amount).toLocaleString('en-IN')}`
}
