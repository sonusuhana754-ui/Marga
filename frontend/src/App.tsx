import { DemoProvider } from '@/state/DemoProvider'
import { SimClockProvider } from '@/state/SimClockProvider'
import { Dashboard } from '@/screens/Dashboard'

export function App() {
  return (
    <DemoProvider>
      <SimClockProvider>
        <Dashboard />
      </SimClockProvider>
    </DemoProvider>
  )
}
