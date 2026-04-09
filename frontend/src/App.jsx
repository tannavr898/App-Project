import { useState, useEffect } from "react"
import Dashboard from "./components/Dashboard"
import LogEntry from "./components/LogEntry"
import Tasks from "./components/Tasks"
import UserSelect from "./components/UserSelect"
import "./index.css"
import { clearAuth, getSavedUser } from "./api"

const LIGHT = {
  "--bg":        "#f7f7f5",
  "--surface":   "#ffffff",
  "--border":    "#e8e6e0",
  "--border-md": "#d4d0c8",
  "--text":      "#1a1a18",
  "--muted":     "#6b6860",
  "--faint":     "#9e9b94",
  "--green":     "#1D9E75",
  "--green-bg":  "#E1F5EE",
  "--green-txt": "#0F6E56",
  "--amber":     "#EF9F27",
  "--amber-bg":  "#FAEEDA",
  "--amber-txt": "#854F0B",
  "--red":       "#D85A30",
  "--red-bg":    "#FAECE7",
  "--red-txt":   "#993C1D",
  "--blue":      "#378ADD",
  "--blue-bg":   "#E6F1FB",
  "--blue-txt":  "#185FA5",
  "--purple":    "#7F77DD",
  "--radius-sm": "6px",
  "--radius-md": "10px",
  "--radius-lg": "14px",
}

const DARK = {
  "--bg":        "#141412",
  "--surface":   "#1e1e1b",
  "--border":    "#2e2e2a",
  "--border-md": "#3e3e38",
  "--text":      "#f0ede6",
  "--muted":     "#b8b4ac",
  "--faint":     "#7a7570",
  "--green":     "#1D9E75",
  "--green-bg":  "#0d3326",
  "--green-txt": "#5DCAA5",
  "--amber":     "#EF9F27",
  "--amber-bg":  "#2e1f06",
  "--amber-txt": "#FAC775",
  "--red":       "#D85A30",
  "--red-bg":    "#2e1208",
  "--red-txt":   "#F0997B",
  "--blue":      "#378ADD",
  "--blue-bg":   "#0a1e35",
  "--blue-txt":  "#85B7EB",
  "--purple":    "#7F77DD",
  "--radius-sm": "6px",
  "--radius-md": "10px",
  "--radius-lg": "14px",
}

export default function App() {
  const [user, setUser] = useState(() => getSavedUser())
  const [page, setPage] = useState("dashboard")
  const [dark, setDark] = useState(() => localStorage.getItem("pulse-theme") === "dark")
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const checkMobile = () => setIsMobile(window.innerWidth <= 640)
    checkMobile()
    window.addEventListener('resize', checkMobile)
    return () => window.removeEventListener('resize', checkMobile)
  }, [])

  const toggleDark = () => {
    setDark(d => {
      const next = !d
      localStorage.setItem("pulse-theme", next ? "dark" : "light")
      return next
    })
  }

  const vars = dark ? DARK : LIGHT

  const navItems = [
    { id: "log",       label: "Log Entry" },
    { id: "dashboard", label: "Overview" },
    { id: "tasks",     label: "Tasks" },
  ]

  return (
    <div style={{
      ...vars,
      minHeight: "100vh",
      background: vars["--bg"],
      color: vars["--text"],
      fontFamily: "'DM Sans', sans-serif",
      transition: "background 0.25s, color 0.25s",
    }}>
      {!user ? (
        <UserSelect onSelect={setUser} />
      ) : isMobile ? (
        // Mobile Layout
        <div className="mobile-app">
          {/* Main Content */}
          <main className="mobile-main">
            {page === "dashboard" && <Dashboard username={user} onNavigate={setPage} />}
            {page === "log"       && <LogEntry  username={user} onSaved={() => setPage("dashboard")} />}
            {page === "tasks"     && <Tasks     username={user} />}
          </main>

          {/* Unified Bottom Bar */}
          <div className="mobile-bottom-bar" style={{display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px", background: "var(--surface)", borderTop: "1px solid var(--border)"}}>
            {/* Profile left */}
            <div className="mobile-profile" style={{display: "flex", alignItems: "center", gap: 10, minWidth: 0}}>
              <div style={{display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 2}}>
                <div className="avatar" style={{width: 36, height: 36, borderRadius: "50%", background: "var(--blue)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, fontWeight: 600}}>{user.slice(0, 2).toUpperCase()}</div>
                <div style={{fontSize: 11, color: "var(--faint)", fontWeight: 500}}>{user}</div>
                <button className="switch-btn" style={{background: "none", border: "none", color: "var(--blue-txt)", fontSize: 11, fontWeight: 500, cursor: "pointer", padding: 0, fontFamily: "inherit", textDecoration: "underline"}} onClick={() => { clearAuth(); setUser(null) }}>Switch account</button>
              </div>
            </div>

            {/* Navigation Tabs center-right */}
            <div className="mobile-tabs" style={{display: "flex", gap: 4}}>
              {navItems.map(item => (
                <button
                  key={item.id}
                  className={`mobile-tab ${page === item.id ? "active" : ""}`}
                  style={{padding: "8px 16px", borderRadius: "var(--radius-md)", border: "1px solid var(--border)", background: page === item.id ? "var(--text)" : "transparent", color: page === item.id ? "var(--bg)" : "var(--muted)", fontSize: 12, fontWeight: 500, cursor: "pointer", fontFamily: "inherit", whiteSpace: "nowrap"}}
                  onClick={() => setPage(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {/* Theme toggle far right */}
            <div style={{display: "flex", alignItems: "center"}}>
              <button className="theme-toggle" style={{width: 40, height: 40, borderRadius: "50%", border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18}} onClick={toggleDark}>
                {dark ? "☀️" : "🌙"}
              </button>
            </div>
          </div>
        </div>
      ) : (
        // Desktop Layout
        <div className="app">
          <aside className="sidebar">
            <div className="logo">
              Pulse
              <span>student wellness</span>
            </div>
            <nav>
              {[
                { id: "dashboard", label: "Overview" },
                { id: "log",       label: "Log entry" },
                { id: "tasks",     label: "Tasks" },
              ].map(item => (
                <button
                  key={item.id}
                  className={`nav-item ${page === item.id ? "active" : ""}`}
                  onClick={() => setPage(item.id)}
                >
                  <span className="nav-dot" />
                  {item.label}
                </button>
              ))}
            </nav>
            <div className="sidebar-footer">
              <div className="avatar">{user.slice(0, 2).toUpperCase()}</div>
              <div className="sidebar-user">
                <span className="sidebar-username">{user}</span>
                <button className="switch-btn" onClick={() => { clearAuth(); setUser(null) }}>switch</button>
              </div>
              <button className="theme-toggle" onClick={toggleDark}>
                {dark ? "☀️ Light" : "🌙 Dark"}
              </button>
            </div>
          </aside>

          <main className="main">
            {page === "dashboard" && <Dashboard username={user} onNavigate={setPage} />}
            {page === "log"       && <LogEntry  username={user} onSaved={() => setPage("dashboard")} />}
            {page === "tasks"     && <Tasks     username={user} />}
          </main>
        </div>
      )}
    </div>
  )
}