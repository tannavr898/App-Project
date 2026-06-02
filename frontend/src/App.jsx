import { useState, useEffect } from "react"
import Dashboard from "./components/Dashboard"
import Companion from "./components/Companion"
import LogEntry from "./components/LogEntry"
import Tasks from "./components/Tasks"
import UserSelect from "./components/UserSelect"
import "./index.css"
import { clearAuth, getSavedUser } from "./api"

const LIGHT = {
  "--bg":        "#F8FAF8",
  "--surface":   "#ffffff",
  "--border":    "#E3EDE7",
  "--border-md": "#C8DBD1",
  "--text":      "#111827",
  "--muted":     "#6B7280",
  "--faint":     "#8B9A93",
  "--green":     "#10B981",
  "--green-bg":  "#DFF8EC",
  "--green-txt": "#047857",
  "--hover":     "#059669",
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
  "--bg":        "#0B1412",
  "--surface":   "#15211D",
  "--border":    "#263832",
  "--border-md": "#375149",
  "--text":      "#F3F4F6",
  "--muted":     "#9CA3AF",
  "--faint":     "#728179",
  "--green":     "#34D399",
  "--green-bg":  "#0E3A2C",
  "--green-txt": "#A7F3D0",
  "--hover":     "#10B981",
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
  const gaMeasurementId = import.meta.env.VITE_GA_MEASUREMENT_ID

  useEffect(() => {
    if (!gaMeasurementId) return
    if (typeof window === "undefined") return
    if (window.gtag) return

    const script = document.createElement("script")
    script.async = true
    script.src = `https://www.googletagmanager.com/gtag/js?id=${gaMeasurementId}`
    document.head.appendChild(script)

    window.dataLayer = window.dataLayer || []
    window.gtag = function gtag(){ window.dataLayer.push(arguments) }
    window.gtag("js", new Date())
    window.gtag("config", gaMeasurementId, { send_page_view: false })
  }, [gaMeasurementId])

  useEffect(() => {
    if (!gaMeasurementId || typeof window === "undefined" || typeof window.gtag !== "function") return
    window.gtag("event", "page_view", {
      page_title: page,
      page_path: `/${page}`,
      page_location: window.location.href,
      user_id: user || "anonymous",
    })
  }, [gaMeasurementId, page, user])

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
    { id: "companion", label: "Companion" },
    { id: "tasks",     label: "Tasks" },
  ]

  return (
    <div style={{
      ...vars,
      height: "100vh",
      background: vars["--bg"],
      color: vars["--text"],
      fontFamily: "'Aptos Rounded', 'Segoe UI Variable', 'Nunito Sans', sans-serif",
      overflow: "hidden",
      transition: "background 0.25s, color 0.25s",
    }}>
      {!user ? (
        <UserSelect onSelect={setUser} />
      ) : isMobile ? (
        <div className="mobile-app" style={{display: "flex", flexDirection: "column", height: "100vh"}}>
          {/* Main Content */}
          <main className="mobile-main" style={{flex: 1, overflowY: "auto", paddingBottom: "70px", background: vars["--bg"]}}>
            {page === "dashboard" && <Dashboard username={user} onNavigate={setPage} />}
            {page === "companion" && <Companion username={user} onNavigate={setPage} />}
            {page === "log"       && <LogEntry  username={user} onSaved={() => setPage("dashboard")} />}
            {page === "tasks"     && <Tasks     username={user} onNavigate={setPage} />}
          </main>

          {/* Fixed Bottom Bar - always visible */}
          <div style={{
            position: "fixed",
            bottom: 0,
            left: 0,
            right: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "8px 12px",
            background: vars["--surface"],
            borderTop: "1px solid var(--border)",
            gap: "8px",
            zIndex: 1000,
            height: "70px",
            boxSizing: "border-box"
          }}>
            {/* Profile: avatar + Switch below */}
            <div style={{display: "flex", flexDirection: "column", alignItems: "center", gap: "4px"}}>
              <div style={{width: "40px", height: "40px", borderRadius: "50%", background: "var(--blue)", color: "white", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "16px", fontWeight: 600}}>{user.slice(0, 2).toUpperCase()}</div>
              <button style={{background: "none", border: "none", color: "var(--blue)", fontSize: "10px", fontWeight: 500, cursor: "pointer", padding: "0", fontFamily: "inherit"}} onClick={() => { clearAuth(); setUser(null) }}>Switch</button>
            </div>

            {/* Tabs - full text, small font, no ellipsis */}
            <div style={{display: "flex", gap: "2px", flex: 1}}>
              {navItems.map(item => (
                <button
                  key={item.id}
                  style={{
                    flex: 1,
                    padding: "6px 8px",
                    borderRadius: "var(--radius-sm)",
                    border: page === item.id ? "1px solid var(--text)" : "1px solid transparent",
                    background: page === item.id ? vars["--text"] : "transparent",
                    color: page === item.id ? vars["--bg"] : vars["--muted"],
                    fontSize: "10px",
                    fontWeight: page === item.id ? "600" : "500",
                    cursor: "pointer",
                    fontFamily: "inherit",
                    whiteSpace: "nowrap",
                    textAlign: "center"
                  }}
                  onClick={() => setPage(item.id)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {/* Theme toggle */}
            <button style={{width: "36px", height: "36px", borderRadius: "50%", border: "1px solid var(--border)", background: vars["--bg"], color: vars["--text"], cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "16px"}} onClick={toggleDark}>
              {dark ? "☀️" : "🌙"}
            </button>
          </div>
        </div>
      ) : (
        // Desktop Layout
        <div className="app">
          <aside className="sidebar">
            <div className="logo">
              <img src="/favicon.svg" alt="Pulse" className="logo-img" />
              <div>
                Pulse
                <span>student wellness</span>
              </div>
            </div>
            <nav>
              {[
                { id: "dashboard", label: "Overview" },
                { id: "log",       label: "Log entry" },
                { id: "companion", label: "Companion" },
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
            {page === "companion" && <Companion username={user} onNavigate={setPage} />}
            {page === "log"       && <LogEntry  username={user} onSaved={() => setPage("dashboard")} />}
            {page === "tasks"     && <Tasks     username={user} onNavigate={setPage} />}
          </main>
        </div>
      )}
    </div>
  )
}

