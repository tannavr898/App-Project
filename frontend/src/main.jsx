import { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'

class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1.5rem', background: '#f7f7f5', color: '#1a1a18', fontFamily: 'DM Sans, sans-serif' }}>
          <div style={{ maxWidth: 640, width: '100%', background: '#fff', border: '1px solid #e8e6e0', borderRadius: 16, padding: '1.5rem', boxShadow: '0 10px 30px rgba(0,0,0,0.08)' }}>
            <h1 style={{ fontSize: 18, marginBottom: 12 }}>Something went wrong</h1>
            <p style={{ fontSize: 14, color: '#6b6860', marginBottom: 16 }}>The app encountered an error while rendering.</p>
            <pre style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 13, color: '#333' }}>{this.state.error?.message}</pre>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/service-worker.js')
      .then(() => console.log('Service worker registered'))
      .catch(err => console.warn('Service worker registration failed:', err))
  })
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </StrictMode>,
)