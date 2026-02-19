import { Analytics } from '@vercel/analytics/react'
import UserApp from './pages/UserApp'

export default function App() {
  return (
    <>
      <UserApp />
      <Analytics />
    </>
  )
}
