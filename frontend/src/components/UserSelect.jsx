import { useState, useEffect, useRef } from "react"

const API = "http://localhost:8000"

export default function UserSelect({ onSelect }) {
  const [users,       setUsers]       = useState([])
  const [newName,     setNewName]     = useState("")
  const [importing,   setImporting]   = useState(false)
  const [importUser,  setImportUser]  = useState("")
  const [message,     setMessage]     = useState(null)
  const fileRef = useRef()

  useEffect(() => {
    fetch(`${API}/users`)
      .then(r => r.json())
      .then(d => setUsers(d.users || []))
      .catch(() => {})
  }, [])

  const handleImport = async (e) => {
    const file = e.target.files[0]
    if (!file || !importUser.trim()) return

    setImporting(true)
    setMessage(null)

    const formData = new FormData()
    formData.append("file", file)

    try {
      const res = await fetch(`${API}/users/${importUser.trim()}/import`, {
        method: "POST",
        body: formData,
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail)
      setMessage({ type: "success", text: `Imported ${data.rows} rows for "${importUser}". You can now select them above.` })
      fetch(`${API}/users`).then(r => r.json()).then(d => setUsers(d.users || []))
    } catch (err) {
      setMessage({ type: "error", text: String(err.message) })
    } finally {
      setImporting(false)
      fileRef.current.value = ""
    }
  }

  return (
    <div className="user-screen">
      <div className="user-card">
        <h2>Pulse</h2>
        <p>Select your profile to continue</p>

        {users.length > 0 && (
          <div className="user-list">
            {users.map(u => (
              <button key={u} className="user-btn" onClick={() => onSelect(u)}>
                {u}
              </button>
            ))}
          </div>
        )}

        {users.length > 0 && <div className="divider">or create new</div>}

        <div className="new-user-row" style={{ marginBottom: "1.25rem" }}>
          <input
            placeholder="Your name"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && newName.trim() && onSelect(newName.trim())}
          />
          <button
            className="btn-primary"
            disabled={!newName.trim()}
            onClick={() => onSelect(newName.trim())}
          >
            Start
          </button>
        </div>

        <div className="divider">or import a csv</div>

        <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: 8 }}>
          <input
            type="text"
            placeholder="Name for this import (e.g. Alex)"
            value={importUser}
            onChange={e => setImportUser(e.target.value)}
            style={{ padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 13, fontFamily: "inherit", background: "var(--surface)", color: "var(--text)", outline: "none" }}
          />
          <label
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              padding: "8px 16px", border: "1px solid var(--border)",
              borderRadius: "var(--radius-sm)", fontSize: 13, cursor: importUser.trim() ? "pointer" : "not-allowed",
              color: importUser.trim() ? "var(--text)" : "var(--faint)",
              background: "var(--surface)", transition: "background 0.15s",
            }}
          >
            {importing ? "Importing…" : "Choose CSV file"}
            <input
              ref={fileRef}
              type="file"
              accept=".csv"
              style={{ display: "none" }}
              disabled={!importUser.trim() || importing}
              onChange={handleImport}
            />
          </label>
          <p style={{ fontSize: 11, color: "var(--faint)", lineHeight: 1.5 }}>
            CSV must have columns: date, sleep_hours, study_hours, training_hours, stress, fatigue, productivity
          </p>
        </div>

        {message && (
          <div style={{
            marginTop: 12, padding: "10px 12px",
            borderRadius: "var(--radius-sm)", fontSize: 12,
            background: message.type === "success" ? "var(--green-bg)" : "var(--red-bg)",
            color: message.type === "success" ? "var(--green-txt)" : "var(--red-txt)",
          }}>
            {message.text}
          </div>
        )}
      </div>
    </div>
  )
}