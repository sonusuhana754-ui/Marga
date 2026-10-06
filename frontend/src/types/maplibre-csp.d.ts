// The CSP build ships without its own types; its surface is identical to the
// main entry, so we alias the types across.
declare module 'maplibre-gl/dist/maplibre-gl-csp' {
  import type maplibregl from 'maplibre-gl'
  const mod: typeof maplibregl
  export default mod
}
