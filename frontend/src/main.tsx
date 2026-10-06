import { createRoot } from 'react-dom/client'
import './index.css'
import { App } from './App'

// Note: React.StrictMode is intentionally omitted. MapLibre GL does not tolerate
// the synchronous mount → unmount → remount cycle StrictMode runs in dev (the
// map's worker pipeline stalls with the style half-initialised). The map layer
// owns its own imperative lifecycle, so we lose little by dropping it here.
createRoot(document.getElementById('root')!).render(<App />)
