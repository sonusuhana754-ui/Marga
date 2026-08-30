import { DemoProvider } from '@/state/DemoProvider'
import { Dashboard } from '@/screens/Dashboard'

export function App() {
  return (
    <DemoProvider>
      <Dashboard />
    </DemoProvider>
  )
}
