import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import { Analytics } from '@vercel/analytics/react'
import './index.css'
import { AuthProvider } from './lib/auth-provider'
import { router } from './router'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <RouterProvider router={router} />
      <Analytics />
    </AuthProvider>
  </StrictMode>,
)
