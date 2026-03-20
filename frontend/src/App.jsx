import { useState } from "react"
import Dashboard from "./components/Dashboard"
import LogEntry from "./components/LogEntry"
import Tasks from "./components/Tasks"
import UserSelect from "./components/UserSelect"
import "./index.css"

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
  const [user, setUser] = useState(null)
  const [page, setPage] = useState("dashboard")
  const [dark, setDark] = useState(() => localStorage.getItem("pulse-theme") === "dark")

  const toggleDark = () => {
    setDark(d => {
      const next = !d
      localStorage.setItem("pulse-theme", next ? "dark" : "light")
      return next
    })
  }

  const vars = dark ? DARK : LIGHT

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
      ) : (
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
                <button className="switch-btn" onClick={() => setUser(null)}>switch</button>
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