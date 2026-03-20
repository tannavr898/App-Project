import { apiFetch } from "../api"
import { useState, useEffect } from "react"

function HourCard({ label, value, onChange, max = 16, step = 0.5, color = "var(--blue)" }) {
  const dec = () => onChange(Math.max(0, Math.round((value - step) * 10) / 10))
  const inc = () => onChange(Math.min(max, Math.round((value + step) * 10) / 10))
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "20px", display: "flex", flexDirection: "column", gap: 12 }}>
      <span style={{ fontSize: 11, color: "var(--faint)", textTransform: "uppercase", letterSpacing: "0.06em" }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <button onClick={dec} style={{ width: 34, height: 34, borderRadius: "50%", border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 20, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit", flexShrink: 0 }}>−</button>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 40, fontWeight: 500, color: "var(--text)", lineHeight: 1 }}>{value.toFixed(1)}</div>
          <div style={{ fontSize: 11, color: "var(--faint)", marginTop: 4 }}>hours</div>
        </div>
        <button onClick={inc} style={{ width: 34, height: 34, borderRadius: "50%", border: "1px solid var(--border)", background: "var(--bg)", color: "var(--text)", fontSize: 20, cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "inherit", flexShrink: 0 }}>+</button>
      </div>
      <div style={{ height: 4, background: "var(--border)", borderRadius: 99, overflow: "hidden" }}>
        <div style={{ height: "100%", width: `${(value / max) * 100}%`, background: color, borderRadius: 99, transition: "width 0.3s ease" }} />
      </div>
    </div>
  )
}

function SliderCard({ label, value, onChange, low, high }) {
  const color = label === "Productivity"
    ? `hsl(${120 + (value - 1) * 8}, 50%, 42%)`
    : `hsl(${28 - (value - 1) * 2}, 70%, 48%)`
  const descriptions = {
    Stress:       ["😌 Totally relaxed", "😐 A little tense", "😰 Pretty stressed", "😤 Very stressed", "🤯 Overwhelmed"],
    Fatigue:      ["⚡ Full of energy",  "🙂 Feeling okay",   "😑 Getting tired",   "😴 Very tired",    "💤 Exhausted"],
    Productivity: ["😞 Couldn't focus",  "🤷 Some progress",  "👍 Decent day",      "💪 Productive",    "🚀 In the zone"],
  }
  const desc = descriptions[label]?.[Math.min(Math.floor((value - 1) / 2.5), 4)]
  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "18px 20px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
        <div>
          <span style={{ fontSize: 14, color: "var(--text)", fontWeight: 500 }}>{label}</span>
          {desc && <span style={{ fontSize: 12, color: "var(--muted)", marginLeft: 8 }}>{desc}</span>}
        </div>
        <span style={{ fontSize: 22, fontWeight: 500, color }}>{value}<span style={{ fontSize: 11, color: "var(--faint)", fontWeight: 400 }}> / 10</span></span>
      </div>
      <input type="range" min="1" max="10" step="1" value={value}
        onChange={e => onChange(parseInt(e.target.value))}
        style={{ width: "100%", accentColor: color }} />
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--faint)", marginTop: 4 }}>
        <span>{low}</span><span>{high}</span>
      </div>
    </div>
  )
}

function StreakBadge({ entries }) {
  if (!entries || entries.length === 0) return null
  let streak = 0
  const today = new Date()
  for (let i = 0; i < 60; i++) {
    const d = new Date(today)
    d.setDate(today.getDate() - i)
    const ds = d.toISOString().split("T")[0]
    if (entries.find(e => e.date?.slice(0, 10) === ds)) streak++
    else if (i > 0) break
  }
  if (streak === 0) return null
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6, background: "var(--amber-bg)", borderRadius: "var(--radius-md)", padding: "6px 12px" }}>
      <span style={{ fontSize: 14 }}>🔥</span>
      <span style={{ fontSize: 12, fontWeight: 500, color: "var(--amber-txt)" }}>{streak} day streak</span>
    </div>
  )
}

function HistoryTable({ entries }) {
  if (!entries || entries.length === 0) return (
    <div style={{ fontSize: 12, color: "var(--faint)", padding: "2rem", textAlign: "center" }}>No entries yet.</div>
  )
  const cols = [
    { key: "date",           label: "Date",         fmt: v => v?.slice(0,10),            color: () => "var(--muted)" },
    { key: "sleep_hours",    label: "Sleep",         fmt: v => `${v}h`,                  color: () => "var(--blue-txt)" },
    { key: "study_hours",    label: "Study",         fmt: v => `${v}h`,                  color: () => "var(--green-txt)" },
    { key: "training_hours", label: "Training",      fmt: v => `${v}h`,                  color: () => "var(--purple)" },
    { key: "stress",         label: "Stress",        fmt: v => `${v} / 10`,              color: v => v >= 7 ? "var(--red-txt)" : v >= 5 ? "var(--amber-txt)" : "var(--green-txt)" },
    { key: "fatigue",        label: "Fatigue",       fmt: v => `${v} / 10`,              color: v => v >= 7 ? "var(--red-txt)" : v >= 5 ? "var(--amber-txt)" : "var(--green-txt)" },
    { key: "productivity",   label: "Productivity",  fmt: v => `${v} / 10`,              color: v => v >= 7 ? "var(--green-txt)" : v >= 5 ? "var(--amber-txt)" : "var(--red-txt)" },
  ]
  const recent = [...entries].reverse().slice(0, 14)
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
        <thead>
          <tr>
            {cols.map(c => (
              <th key={c.key} style={{ textAlign: "left", fontSize: 10, color: "var(--faint)", textTransform: "uppercase", letterSpacing: "0.05em", padding: "0 8px 10px 0", fontWeight: 500, whiteSpace: "nowrap" }}>{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {recent.map((row, i) => (
            <tr key={i} style={{ borderTop: "1px solid var(--border)" }}>
              {cols.map(c => (
                <td key={c.key} style={{ padding: "10px 8px 10px 0", color: c.color(row[c.key]), whiteSpace: "nowrap" }}>
                  {c.fmt(row[c.key])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default function LogEntry({ username, onSaved }) {
  const today = new Date().toISOString().split("T")[0]

  const [tab,      setTab]      = useState("log")
  const [date,     setDate]     = useState(today)
  const [sleep,    setSleep]    = useState(8.0)
  const [study,    setStudy]    = useState(3.0)
  const [training, setTraining] = useState(1.0)
  const [stress,   setStress]   = useState(5)
  const [fatigue,  setFatigue]  = useState(5)
  const [prod,     setProd]     = useState(7)
  const [saving,   setSaving]   = useState(false)
  const [saved,    setSaved]    = useState(false)
  const [error,    setError]    = useState(null)
  const [entries,  setEntries]  = useState([])

  const [prefill, setPrefill] = useState(null)

  useEffect(() => {
    apiFetch(`/users/${username}/entries`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.entries) setEntries(d.entries) })
      .catch(() => {})
    apiFetch(`/tasks/${username}/prefill`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d) {
          setPrefill(d)
          if (d.hours_by_category?.study > 0)    setStudy(d.hours_by_category.study)
          if (d.hours_by_category?.training > 0) setTraining(d.hours_by_category.training)
        }
      })
      .catch(() => {})
  }, [username])

  const totalHours = sleep + study + training
  const remaining  = 24 - totalHours

  const handleSubmit = async () => {
    setSaving(true); setError(null)
    try {
      const res = await apiFetch(`/entries`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, date, sleep_hours: sleep, study_hours: study, training_hours: training, stress, fatigue, productivity: prod }),
      })
      if (!res.ok) throw new Error()
      setSaved(true)
      setTimeout(() => onSaved(), 900)
    } catch { setError("Could not save. Is the backend running?") }
    finally   { setSaving(false) }
  }

  if (saved) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "60vh", flexDirection: "column", gap: 12 }}>
      <div style={{ fontSize: 40 }}>✓</div>
      <p style={{ color: "var(--green-txt)", fontSize: 14 }}>Entry saved! Returning to dashboard…</p>
    </div>
  )

  return (
    <div style={{ width: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div>
            <h1 style={{ fontSize: 16, fontWeight: 500, color: "var(--text)" }}>Log entry</h1>
            <p style={{ fontSize: 12, color: "var(--faint)", marginTop: 2 }}>Track your daily wellness</p>
          </div>
          <StreakBadge entries={entries} />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <div style={{ display: "flex", background: "var(--bg)", borderRadius: "var(--radius-md)", padding: 3, border: "1px solid var(--border)" }}>
            {["log", "history"].map(t => (
              <button key={t} onClick={() => setTab(t)} style={{ padding: "5px 16px", borderRadius: "var(--radius-sm)", border: "none", background: tab === t ? "var(--surface)" : "transparent", color: tab === t ? "var(--text)" : "var(--faint)", fontSize: 12, cursor: "pointer", fontFamily: "inherit", fontWeight: tab === t ? 500 : 400, transition: "all 0.15s" }}>
                {t === "log" ? "Log" : "History"}
              </button>
            ))}
          </div>
          {tab === "log" && (
            <input type="date" value={date} onChange={e => setDate(e.target.value)}
              style={{ padding: "6px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 13, background: "var(--surface)", color: "var(--text)", fontFamily: "inherit", outline: "none" }} />
          )}
        </div>
      </div>

      {tab === "history" ? (
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>Recent entries</span>
            <span style={{ fontSize: 11, color: "var(--faint)" }}>{entries.length} total</span>
          </div>
          <HistoryTable entries={entries} />
        </div>
      ) : (
        <>
          {/* Hours */}
          <div style={{ marginBottom: "1.5rem" }}>
            <div style={{ fontSize: 11, fontWeight: 500, color: "var(--faint)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>Hours</div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12 }}>
              <HourCard label="Sleep"    value={sleep}    onChange={setSleep}    max={14} color="var(--blue)"   />
              <HourCard label="Study"    value={study}    onChange={setStudy}    max={12} color="var(--green)"  />
              <HourCard label="Training" value={training} onChange={setTraining} max={6}  color="var(--purple)" />
            </div>
            <div style={{ marginTop: 10, padding: "10px 14px", background: "var(--bg)", borderRadius: "var(--radius-md)", display: "flex", justifyContent: "space-between", fontSize: 12 }}>
              <span style={{ color: "var(--muted)" }}>Total logged: <strong style={{ color: "var(--text)" }}>{totalHours.toFixed(1)}h</strong></span>
              <span style={{ color: remaining < 4 ? "var(--amber-txt)" : "var(--faint)" }}>{remaining.toFixed(1)}h unaccounted for</span>
            </div>
            {prefill && (prefill.hours_by_category?.study > 0 || prefill.hours_by_category?.training > 0) && (
              <div style={{ marginTop: 8, padding: "10px 14px", background: "var(--green-bg)", borderRadius: "var(--radius-md)", display: "flex", justifyContent: "space-between", alignItems: "center", fontSize: 12 }}>
                <span style={{ color: "var(--green-txt)" }}>
                  ✓ Pre-filled from today's completed tasks
                </span>
                <span style={{ color: "var(--green-txt)", opacity: 0.8, fontSize: 11 }}>
                  {prefill.hours_by_category.study > 0 && `${prefill.hours_by_category.study}h study`}
                  {prefill.hours_by_category.study > 0 && prefill.hours_by_category.training > 0 && " · "}
                  {prefill.hours_by_category.training > 0 && `${prefill.hours_by_category.training}h training`}
                </span>
              </div>
            )}
          </div>

          {/* Ratings */}
          <div style={{ marginBottom: "1.5rem" }}>
            <div style={{ fontSize: 11, fontWeight: 500, color: "var(--faint)", textTransform: "uppercase", letterSpacing: "0.06em", marginBottom: 12 }}>How did you feel?</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <SliderCard label="Stress"       value={stress}  onChange={setStress}  low="Very calm"       high="Overwhelmed"           />
              <SliderCard label="Fatigue"      value={fatigue} onChange={setFatigue} low="Full of energy"  high="Completely exhausted"  />
              <SliderCard label="Productivity" value={prod}    onChange={setProd}    low="Couldn't focus"  high="Extremely productive"  />
            </div>
          </div>

          {error && <p style={{ fontSize: 12, color: "var(--red-txt)", marginBottom: 12 }}>{error}</p>}

          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button onClick={handleSubmit} disabled={saving}
              style={{ background: "var(--text)", color: "var(--bg)", border: "none", borderRadius: "var(--radius-sm)", padding: "11px 40px", fontSize: 14, fontFamily: "inherit", fontWeight: 500, cursor: saving ? "not-allowed" : "pointer", opacity: saving ? 0.5 : 1 }}>
              {saving ? "Saving…" : "Save entry"}
            </button>
          </div>
        </>
      )}
    </div>
  )
}