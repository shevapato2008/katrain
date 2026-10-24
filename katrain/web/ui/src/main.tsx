import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/theme.css'
import './styles/global.css'
import './index.css'
import AppRouter from './AppRouter.tsx'

// A kiosk tab can remain open while a deployment replaces Vite's hashed chunks.
// Reload the current route against the new index instead of leaving React blank.
window.addEventListener('vite:preloadError', (event) => {
  event.preventDefault()
  window.location.reload()
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppRouter />
  </StrictMode>,
)
