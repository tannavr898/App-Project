import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then(() => console.log('Service worker registered'))
      .catch(err => console.warn('Service worker registration failed:', err))
  })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)