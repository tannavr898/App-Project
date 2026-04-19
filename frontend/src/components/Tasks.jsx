import { apiFetch, clearApiCache, getCachedJson } from "../api"
import { useState, useEffect, useRef } from "react"

const getLocalDate = date => {
  // If it's already a date string (YYYY-MM-DD), return as-is to avoid timezone issues
  if (typeof date === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(date)) return date
  // For Date objects, convert to local date string
  return new Date(date).toLocaleDateString("en-CA")
}

const getClientToday = () => getLocalDate(new Date())

const CATEGORIES = [
  { id: "study",    label: "Study",    color: "var(--green)",  bg: "var(--green-bg)",  txt: "var(--green-txt)" },
  { id: "training", label: "Training", color: "var(--purple)", bg: "#EEEDFE",          txt: "#534AB7" },
  { id: "personal", label: "Personal", color: "var(--blue)",   bg: "var(--blue-bg)",   txt: "var(--blue-txt)" },
  { id: "other",    label: "Other",    color: "var(--amber)",  bg: "var(--amber-bg)",  txt: "var(--amber-txt)" },
]

function getCat(id) {
  return CATEGORIES.find(c => c.id === id) || CATEGORIES[3]
}

function CircleProgress({ pct, size = 80, stroke = 7 }) {
  const r = (size - stroke) / 2
  const circ = 2 * Math.PI * r
  const filled = circ * Math.min(1, pct / 100)
  const color = pct >= 100 ? "var(--green)" : pct >= 50 ? "var(--blue)" : "var(--amber)"
  return (
    <svg width={size} height={size} style={{ transform: "rotate(-90deg)" }}>
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke="var(--border)" strokeWidth={stroke} />
      <circle cx={size/2} cy={size/2} r={r} fill="none" stroke={color} strokeWidth={stroke}
        strokeDasharray={`${filled} ${circ}`} strokeLinecap="round"
        style={{ transition: "stroke-dasharray 0.8s ease" }} />
    </svg>
  )
}

function WeeklyBar({ date, rate }) {
  // date is a string like "2026-04-08"
  // Parse it correctly in local timezone to get the day of week
  const [year, month, day] = date.split('-').map(Number)
  const d = new Date(year, month - 1, day)
  const dayChar = d.toLocaleDateString("en-US", { weekday: "short" }).slice(0, 1)
  const today = new Date().toLocaleDateString("en-CA")
  const isToday = date === today
  const color = rate >= 0.9 ? "var(--green)" : rate >= 0.5 ? "var(--blue)" : rate > 0 ? "var(--amber)" : "var(--border)"
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <div style={{ width: 24, height: 48, background: "var(--border)", borderRadius: 99, overflow: "hidden", display: "flex", alignItems: "flex-end", border: isToday ? `2px solid ${color}` : "none", boxSizing: "border-box" }}>
        <div style={{ width: "100%", height: `${Math.max(4, rate * 100)}%`, background: color, borderRadius: 99, transition: "height 0.6s ease" }} />
      </div>
      <span style={{ fontSize: 9, color: "var(--faint)", fontWeight: isToday ? 500 : 400 }}>{dayChar}</span>
    </div>
  )
}

export default function Tasks({ username }) {
  const cachedAnalysis = getCachedJson(`analysis:${username}`, 90000)
  const initialRecHours = cachedAnalysis?.optimal_plan?.study ?? 3.5

  const [tasks,    setTasks]    = useState([])
  const [progress, setProgress] = useState(null)
  const [recHours, setRecHours] = useState(initialRecHours)
  const [history,  setHistory]  = useState({})
  const [loading,  setLoading]  = useState(true)
  const [filter,   setFilter]   = useState("all")

  const [newName,      setNewName]      = useState("")
  const [newHours,     setNewHours]     = useState(1)
  const [newCarryOver, setNewCarryOver] = useState(true)
  const [newCat,       setNewCat]       = useState("study")
  const [adding,       setAdding]       = useState(false)
  const [actionPending, setActionPending] = useState(false)
  const [freeHours,    setFreeHours]    = useState(null)
  const [taskError,    setTaskError]    = useState("")
  const actionLockRef = useRef(false)
  const loadSequenceRef = useRef(0)

  const extractError = async response => {
    try {
      const data = await response.json()
      if (typeof data?.detail === "string") return data.detail
      return `Request failed (${response.status})`
    } catch {
      return `Request failed (${response.status})`
    }
  }

  const load = async () => {
    const requestId = ++loadSequenceRef.current
    try {
      setTaskError("")
      const today = getClientToday()
      const r = await apiFetch(`/tasks/${username}?recommended_hours=${recHours}&today=${today}`, {
        timeoutMs: 20000,
      })
      if (!r.ok) {
        throw new Error(await extractError(r))
      }
      const d = await r.json()
      if (requestId !== loadSequenceRef.current) return
      setTasks(d.tasks || [])
      setProgress(d.progress || null)
    } catch (err) {
      if (requestId !== loadSequenceRef.current) return
      setTaskError(err?.message || "Could not load tasks")
    } finally {
      if (requestId !== loadSequenceRef.current) return
      setLoading(false)
    }
  }

  useEffect(() => {
    // Fetch selected plan mode from localStorage
    const selectedMode = localStorage.getItem(`pulse-plan-${username}`)
    clearApiCache(key => key.startsWith(`tasks:${username}:`) || key.startsWith(`task-history:${username}`) || key.startsWith(`task-prefill:${username}`))
    
    apiFetch(`/users/${username}/analysis`, {
      cacheKey: `analysis:${username}`,
      cacheTtlMs: 90000,
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.plans && selectedMode) {
          // Use the selected mode's study hours
          const selectedPlan = d.plans[selectedMode]
          if (selectedPlan?.study) {
            setRecHours(selectedPlan.study)
          } else if (d?.optimal_plan?.study) {
            setRecHours(d.optimal_plan.study)
          }
        } else if (d?.optimal_plan?.study) {
          setRecHours(d.optimal_plan.study)
        }
      })
      .catch(() => {})
    const today = getClientToday()

    apiFetch(`/tasks/${username}/history?today=${today}`, {
      cacheKey: `task-history:${username}`,
      cacheTtlMs: 90000,
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.history) setHistory(d.history) })
      .catch(() => {})
    apiFetch(`/tasks/${username}/prefill?today=${today}`, {
      cacheKey: `task-prefill:${username}`,
      cacheTtlMs: 90000,
    })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.free_hours_yesterday != null) setFreeHours(d.free_hours_yesterday) })
      .catch(() => {})
  }, [username])

  // Re-fetch tasks when recHours changes OR when selected plan changes
  useEffect(() => {
    const selectedMode = localStorage.getItem(`pulse-plan-${username}`)
    load()
  }, [username, recHours])

  // Listen for plan changes made on the Dashboard
  useEffect(() => {
    const handleStorageChange = () => {
      const selectedMode = localStorage.getItem(`pulse-plan-${username}`)
      if (selectedMode) {
        apiFetch(`/users/${username}/analysis`, {
          cacheKey: `analysis:${username}`,
          cacheTtlMs: 90000,
        })
          .then(r => r.ok ? r.json() : null)
          .then(d => {
            if (d?.plans?.[selectedMode]?.study) {
              setRecHours(d.plans[selectedMode].study)
            }
          })
          .catch(() => {})
      }
    }
    
    window.addEventListener("storage", handleStorageChange)
    return () => window.removeEventListener("storage", handleStorageChange)
  }, [username])

  const addTask = async () => {
    if (!newName.trim() || !Number.isFinite(newHours) || newHours <= 0 || adding || actionPending || actionLockRef.current) return
    actionLockRef.current = true
    setAdding(true)
    setActionPending(true)
    try {
      setTaskError("")
      const response = await apiFetch(`/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username,
          name: newName.trim(),
          hours: newHours,
          carry_over: newCarryOver,
          category: newCat,
          today: getClientToday(),
        }),
      })
      if (!response.ok) {
        throw new Error(await extractError(response))
      }
      clearApiCache(key => key.startsWith(`tasks:${username}`) || key.startsWith(`task-history:${username}`) || key.startsWith(`task-prefill:${username}`) || key.includes(`/tasks/${username}`) || key.includes(`/users/${username}/analysis`))
      setNewName("")
      setNewHours(1)
      setNewCarryOver(true)
      await load()
    } catch (err) {
      setTaskError(err?.message || "Could not add task")
    } finally {
      actionLockRef.current = false
      setAdding(false)
      setActionPending(false)
    }
  }

  const toggleComplete = async task => {
    if (actionPending || actionLockRef.current) return
    actionLockRef.current = true
    setActionPending(true)
    try {
      setTaskError("")
      const response = await apiFetch(`/tasks/${task.completed ? "uncomplete" : "complete"}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, task_id: task.id, today: getClientToday() }),
      })
      if (!response.ok) {
        throw new Error(await extractError(response))
      }
      clearApiCache(key => key.startsWith(`tasks:${username}`) || key.startsWith(`task-history:${username}`) || key.startsWith(`task-prefill:${username}`) || key.includes(`/tasks/${username}`) || key.includes(`/users/${username}/analysis`))
      await load()
    } catch (err) {
      setTaskError(err?.message || "Could not update task")
      await load()
    } finally {
      actionLockRef.current = false
      setActionPending(false)
    }
  }

  const deleteTask = async id => {
    if (actionPending || actionLockRef.current) return
    actionLockRef.current = true
    setActionPending(true)
    try {
      setTaskError("")
      const response = await apiFetch(`/tasks/${username}/${id}?today=${getClientToday()}`, { method: "DELETE" })
      if (!response.ok) {
        throw new Error(await extractError(response))
      }
      clearApiCache(key => key.startsWith(`tasks:${username}`) || key.startsWith(`task-history:${username}`) || key.startsWith(`task-prefill:${username}`) || key.includes(`/tasks/${username}`) || key.includes(`/users/${username}/analysis`))
      await load()
    } catch (err) {
      setTaskError(err?.message || "Could not delete task")
      await load()
    } finally {
      actionLockRef.current = false
      setActionPending(false)
    }
  }

  const toggleCarryOver = async task => {
    if (actionPending || actionLockRef.current) return
    actionLockRef.current = true
    setActionPending(true)
    try {
      setTaskError("")
      const response = await apiFetch(`/tasks/toggle-carry-over`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, task_id: task.id, today: getClientToday() }),
      })
      if (!response.ok) {
        throw new Error(await extractError(response))
      }
      clearApiCache(key => key.startsWith(`tasks:${username}`) || key.startsWith(`task-history:${username}`) || key.startsWith(`task-prefill:${username}`) || key.includes(`/tasks/${username}`) || key.includes(`/users/${username}/analysis`))
      await load()
    } catch (err) {
      setTaskError(err?.message || "Could not update carry-over")
      await load()
    } finally {
      actionLockRef.current = false
      setActionPending(false)
    }
  }

  if (loading) return <div className="loading">Loading tasks…</div>

  const pct        = progress?.progress_pct ?? 0
  const barColor   = pct >= 100 ? "var(--green)" : pct >= 50 ? "var(--blue)" : "var(--amber)"
  const completed  = tasks.filter(t => t.completed)
  const pending    = tasks.filter(t => !t.completed)
  const totalHours = tasks.reduce((s, t) => s + t.hours, 0)

  // Calculate completion streak
  let streak = 0
  const today = getLocalDate(new Date())
  const historyEntries = Object.entries(history).sort((a, b) => new Date(b[0]) - new Date(a[0]))
  for (const [date, rate] of historyEntries) {
    if (rate >= 0.9) {
      const daysDiff = Math.floor((new Date(today) - new Date(date)) / (1000 * 60 * 60 * 24))
      if (daysDiff === streak) {
        streak++
      } else {
        break
      }
    } else {
      break
    }
  }

  // build last 7 days for weekly chart (today shows current progress, not finalized history)
  const last7 = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(); d.setDate(new Date().getDate() - 6 + i)
    const key = getLocalDate(d)
    const rate = history[key] ?? 0
    return { date: key, rate }
  })

  const filtered = filter === "all" ? tasks
    : filter === "done" ? completed
    : filter === "pending" ? pending
    : tasks.filter(t => (t.category || "other") === filter)

  return (
    <div style={{ width: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem" }}>
        <div>
          <h1 style={{ fontSize: 16, fontWeight: 500, color: "var(--text)" }}>Tasks</h1>
          <p style={{ fontSize: 12, color: "var(--faint)", marginTop: 2 }}>Track your daily study goal</p>
        </div>
      </div>

      <div className="tasks-grid">

        {/* LEFT — task list */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>

          {/* Progress bar card */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ position: "relative", flexShrink: 0 }}>
                <CircleProgress pct={pct} size={72} stroke={6} />
                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column" }}>
                  <span style={{ fontSize: 14, fontWeight: 500, color: "var(--text)", lineHeight: 1 }}>{Math.round(pct)}%</span>
                </div>
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 6 }}>
                  <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>Today's goal</span>
                  <span style={{ fontSize: 13, color: "var(--faint)" }}>
                    {progress?.completed_hours ?? 0}h <span style={{ color: "var(--faint)" }}>/ {recHours}h</span>
                  </span>
                </div>
                <div style={{ height: 6, background: "var(--border)", borderRadius: 99, overflow: "hidden", marginBottom: 8 }}>
                  <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 99, transition: "width 0.8s ease" }} />
                </div>
                <div style={{ display: "flex", gap: 16, fontSize: 11, color: "var(--faint)" }}>
                  <span style={{ color: "var(--green-txt)" }}>✓ {completed.length} done</span>
                  <span>{pending.length} pending</span>
                  <span>{pct >= 100 ? "🎉 Goal reached!" : `${progress?.remaining_hours ?? recHours}h remaining`}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Filter tabs */}
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {[
              { id: "all",     label: `All (${tasks.length})` },
              { id: "pending", label: `Pending (${pending.length})` },
              { id: "done",    label: `Done (${completed.length})` },
              ...CATEGORIES.map(c => ({ id: c.id, label: c.label })),
            ].map(f => (
              <button key={f.id} onClick={() => setFilter(f.id)} style={{
                padding: "4px 12px", borderRadius: 99, fontSize: 11, cursor: "pointer", fontFamily: "inherit",
                border: "1px solid var(--border)",
                background: filter === f.id ? "var(--text)" : "var(--surface)",
                color: filter === f.id ? "var(--bg)" : "var(--muted)",
                transition: "all 0.15s",
              }}>{f.label}</button>
            ))}
          </div>

          {/* Task list */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem" }}>
            {taskError && (
              <div style={{ marginBottom: 10, fontSize: 12, color: "var(--red-txt)", background: "var(--red-bg)", border: "1px solid var(--red)", borderRadius: "var(--radius-sm)", padding: "8px 10px" }}>
                {taskError}
              </div>
            )}
            {filtered.length === 0 && (
              <p style={{ fontSize: 12, color: "var(--faint)", padding: "8px 0" }}>No tasks here yet.</p>
            )}

            {filtered.map(task => {
              const cat = getCat(task.category || "other")
              return (
                <div key={task.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0", borderBottom: "1px solid var(--border)", opacity: actionPending ? 0.7 : 1 }}
                  className="task-item">
                  {/* Checkbox */}
                  <div onClick={() => !actionPending && toggleComplete(task)} style={{
                    width: 16, height: 16, borderRadius: 4, flexShrink: 0, cursor: actionPending ? "not-allowed" : "pointer",
                    border: task.completed ? "none" : "1px solid var(--border-md)",
                    background: task.completed ? "var(--green)" : "transparent",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    transition: "all 0.15s",
                    pointerEvents: actionPending ? "none" : "auto",
                  }}>
                    {task.completed && <div style={{ width: 5, height: 3, borderLeft: "1.5px solid white", borderBottom: "1.5px solid white", transform: "rotate(-45deg) translateY(-1px)" }} />}
                  </div>

                  {/* Category dot */}
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: cat.color, flexShrink: 0 }} />

                  {/* Name */}
                  <span style={{ flex: 1, fontSize: 13, color: task.completed ? "var(--faint)" : "var(--text)", textDecoration: task.completed ? "line-through" : "none" }}>
                    {task.name}
                  </span>

                  {/* Category badge */}
                  <span style={{ fontSize: 10, padding: "2px 7px", borderRadius: 99, background: cat.bg, color: cat.txt, flexShrink: 0 }}>
                    {cat.label}
                  </span>

                  {/* Hours */}
                  <span style={{ fontSize: 11, color: "var(--faint)", minWidth: 28, textAlign: "right" }}>{task.hours}h</span>

                  {/* Carry over */}
                  <button disabled={actionPending} onClick={() => toggleCarryOver(task)} title={task.carry_over ? "Carry-over on" : "Carry-over off"}
                    style={{ background: "none", border: "none", cursor: actionPending ? "not-allowed" : "pointer", fontSize: 13, color: task.carry_over ? "var(--blue-txt)" : "var(--faint)", padding: 0, lineHeight: 1, opacity: actionPending ? 0.45 : 1 }}>
                    ↺
                  </button>

                  {/* Delete */}
                  <button disabled={actionPending} className="task-delete" onClick={() => deleteTask(task.id)}>×</button>
                </div>
              )
            })}

            {/* Add task */}
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                <div style={{ fontSize: 11, color: "var(--faint)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Add task</div>
                {freeHours !== null && (
                  <div style={{ fontSize: 11, color: totalHours > freeHours ? "var(--red-txt)" : "var(--green-txt)", background: totalHours > freeHours ? "var(--red-bg)" : "var(--green-bg)", padding: "2px 8px", borderRadius: 99 }}>
                    {totalHours > freeHours
                      ? `${(totalHours - freeHours).toFixed(1)}h over capacity`
                      : `${(freeHours - totalHours).toFixed(1)}h available today`}
                  </div>
                )}
              </div>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <input type="text" placeholder="Task name" value={newName}
                  onChange={e => setNewName(e.target.value)}
                  onKeyDown={e => e.key === "Enter" && addTask()}
                  style={{ flex: 1, minWidth: 160, padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 13, background: "var(--surface)", color: "var(--text)", fontFamily: "inherit", outline: "none" }} />
                <input type="number" min="0.25" max="12" step="0.25" value={newHours}
                  onChange={e => setNewHours(parseFloat(e.target.value))}
                  title="Hours"
                  style={{ width: 64, padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 13, background: "var(--surface)", color: "var(--text)", fontFamily: "inherit", outline: "none" }} />
                <select value={newCat} onChange={e => setNewCat(e.target.value)}
                  style={{ padding: "8px 10px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 12, background: "var(--surface)", color: "var(--text)", fontFamily: "inherit", outline: "none", cursor: "pointer" }}>
                  {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                </select>
                <button onClick={() => setNewCarryOver(c => !c)}
                  disabled={actionPending}
                  style={{ padding: "8px 12px", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 11, background: newCarryOver ? "var(--blue-bg)" : "var(--surface)", color: newCarryOver ? "var(--blue-txt)" : "var(--faint)", cursor: actionPending ? "not-allowed" : "pointer", fontFamily: "inherit", transition: "all 0.15s", opacity: actionPending ? 0.45 : 1 }}>
                  ↺ carry over
                </button>
                <button onClick={addTask} disabled={adding || actionPending || !newName.trim()}
                  style={{ padding: "8px 18px", background: "var(--text)", color: "var(--bg)", border: "none", borderRadius: "var(--radius-sm)", fontSize: 13, fontFamily: "inherit", fontWeight: 500, cursor: adding || actionPending || !newName.trim() ? "not-allowed" : "pointer", opacity: adding || actionPending || !newName.trim() ? 0.4 : 1 }}>
                  Add
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* RIGHT — stats panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>

          {/* Today's stats */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem" }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)", marginBottom: "1rem" }}>Today's stats</div>
            {[
              { label: "Tasks completed",  value: `${completed.length} / ${tasks.length}`, color: "var(--green-txt)" },
              { label: "Hours logged",     value: `${progress?.completed_hours ?? 0}h`,    color: "var(--blue-txt)" },
              { label: "Hours remaining",  value: `${progress?.remaining_hours ?? recHours}h`, color: pct >= 100 ? "var(--green-txt)" : "var(--amber-txt)" },
              { label: "Total task hours", value: `${totalHours.toFixed(1)}h`,             color: "var(--muted)" },
            ].map(s => (
              <div key={s.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                <span style={{ fontSize: 12, color: "var(--muted)" }}>{s.label}</span>
                <span style={{ fontSize: 14, fontWeight: 500, color: s.color }}>{s.value}</span>
              </div>
            ))}
          </div>

          {/* Streak */}
          {streak > 0 && (
            <div style={{ background: "var(--green-bg)", border: "1px solid var(--green-txt)", borderRadius: "var(--radius-lg)", padding: "1.25rem", textAlign: "center" }}>
              <div style={{ fontSize: 12, color: "var(--green-txt)", marginBottom: 4 }}>🔥 Streak</div>
              <div style={{ fontSize: 28, fontWeight: 500, color: "var(--green-txt)", lineHeight: 1 }}>{streak}</div>
              <div style={{ fontSize: 11, color: "var(--green-txt)", marginTop: 4, opacity: 0.85 }}>day{streak !== 1 ? "s" : ""} in a row</div>
            </div>
          )}

          {/* Category breakdown */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem" }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)", marginBottom: "1rem" }}>By category</div>
            {CATEGORIES.map(cat => {
              const catTasks = tasks.filter(t => (t.category || "other") === cat.id)
              const catDone  = catTasks.filter(t => t.completed).length
              const catHours = catTasks.reduce((s, t) => s + t.hours, 0)
              if (catTasks.length === 0) return null
              return (
                <div key={cat.id} style={{ marginBottom: 10 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: cat.color }} />
                      <span>{cat.label}</span>
                    </div>
                    <span>{catDone}/{catTasks.length} · {catHours.toFixed(1)}h</span>
                  </div>
                  <div style={{ height: 4, background: "var(--border)", borderRadius: 99, overflow: "hidden" }}>
                    <div style={{ height: "100%", width: catTasks.length > 0 ? `${(catDone/catTasks.length)*100}%` : "0%", background: cat.color, borderRadius: 99, transition: "width 0.6s ease" }} />
                  </div>
                </div>
              )
            })}
            {tasks.length === 0 && <p style={{ fontSize: 12, color: "var(--faint)" }}>No tasks yet.</p>}
          </div>

          {/* Weekly history */}
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem" }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)", marginBottom: "1rem" }}>Weekly completion</div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", padding: "0 4px" }}>
              {last7.map((d, i) => {
                const rate = i === 6 && pct > 0 ? Math.min(pct / 100, progress?.progress_pct / 100 || 0) : d.rate
                return <WeeklyBar key={d.date} date={d.date} rate={rate} />
              })}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, fontSize: 10, color: "var(--faint)" }}>
              <span>7 days ago</span>
              <span>today</span>
            </div>
          </div>

          {/* Carry-over notice */}
          {tasks.filter(t => t.carry_over && !t.completed).length > 0 && (
            <div style={{ background: "var(--amber-bg)", border: "1px solid var(--amber)", borderRadius: "var(--radius-lg)", padding: "1rem 1.25rem" }}>
              <div style={{ fontSize: 12, fontWeight: 500, color: "var(--amber-txt)", marginBottom: 4 }}>↺ Carry-over tasks</div>
              <div style={{ fontSize: 11, color: "var(--amber-txt)", opacity: 0.8 }}>
                {tasks.filter(t => t.carry_over && !t.completed).length} task{tasks.filter(t => t.carry_over && !t.completed).length > 1 ? "s" : ""} will roll over to tomorrow if not completed.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}