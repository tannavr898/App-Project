import { useState } from "react"
import { login, register, saveAuth } from "../api"

export default function UserSelect({ onSelect }) {
  const [mode,     setMode]     = useState("login")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [confirm,  setConfirm]  = useState("")
  const [loading,  setLoading]  = useState(false)
  const [error,    setError]    = useState(null)

  const handleSubmit = async () => {
    setError(null)
    if (!username.trim() || !password) { setError("Please fill in all fields."); return }
    if (mode === "register" && password !== confirm) { setError("Passwords don't match."); return }
    if (mode === "register" && password.length < 6)  { setError("Password must be at least 6 characters."); return }

    setLoading(true)
    try {
      const fn   = mode === "login" ? login : register
      const data = await fn(username.trim().toLowerCase(), password)
      saveAuth(data.username, data.token)
      onSelect(data.username)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const inputStyle = {
    width: "100%", padding: "9px 12px",
    border: "1px solid var(--border)", borderRadius: "var(--radius-sm)",
    fontSize: 13, fontFamily: "inherit",
    background: "var(--surface)", color: "var(--text)", outline: "none",
  }

  return (
    <div className="user-screen">
      <div className="user-card">

        {/* Logo */}
        <div style={{ marginBottom: "1.5rem" }}>
          <h2 style={{ fontSize: 20, fontWeight: 500, color: "var(--text)" }}>Pulse</h2>
          <p style={{ fontSize: 12, color: "var(--faint)", marginTop: 2 }}>student wellness</p>
        </div>

        {/* Tab switcher */}
        <div style={{ display: "flex", background: "var(--bg)", borderRadius: "var(--radius-md)", padding: 3, border: "1px solid var(--border)", marginBottom: "1.25rem" }}>
          {["login", "register"].map(m => (
            <button key={m} onClick={() => { setMode(m); setError(null) }} style={{
              flex: 1, padding: "6px 0", borderRadius: "var(--radius-sm)",
              border: "none", fontSize: 12, cursor: "pointer", fontFamily: "inherit",
              background: mode === m ? "var(--surface)" : "transparent",
              color: mode === m ? "var(--text)" : "var(--faint)",
              fontWeight: mode === m ? 500 : 400, transition: "all 0.15s",
            }}>
              {m === "login" ? "Sign in" : "Create account"}
            </button>
          ))}
        </div>

        {/* Form */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <input
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSubmit()}
            autoFocus
            style={inputStyle}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSubmit()}
            style={inputStyle}
          />
          {mode === "register" && (
            <input
              type="password"
              placeholder="Confirm password"
              value={confirm}
              onChange={e => setConfirm(e.target.value)}
              onKeyDown={e => e.key === "Enter" && handleSubmit()}
              style={inputStyle}
            />
          )}
        </div>

        {error && (
          <div style={{ marginTop: 10, padding: "8px 12px", background: "var(--red-bg)", borderRadius: "var(--radius-sm)", fontSize: 12, color: "var(--red-txt)" }}>
            {error}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading}
          style={{ marginTop: 14, width: "100%", padding: "10px", background: "var(--text)", color: "var(--bg)", border: "none", borderRadius: "var(--radius-sm)", fontSize: 13, fontFamily: "inherit", fontWeight: 500, cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.5 : 1 }}
        >
          {loading ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
        </button>

        {mode === "login" && (
          <p style={{ marginTop: 12, fontSize: 11, color: "var(--faint)", textAlign: "center" }}>
            New here?{" "}
            <button onClick={() => { setMode("register"); setError(null) }}
              style={{ background: "none", border: "none", color: "var(--blue-txt)", cursor: "pointer", fontSize: 11, fontFamily: "inherit" }}>
              Create an account
            </button>
          </p>
        )}
      </div>
    </div>
  )
}