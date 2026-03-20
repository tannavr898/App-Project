import { useState, useEffect, useRef } from "react"

const API = "http://localhost:8000"

function Sparkline({ data, keyPerf, keyBurnout }) {
  const svgRef = useRef(null)
  const [hover, setHover] = useState(null)

  if (!data || data.length < 2) return null

  const W = 500, H = 220
  const padLeft = 44, padRight = 16, padTop = 28, padBottom = 28

  const perfVals    = data.map(d => d[keyPerf]   ?? 0)
  const burnoutVals = data.map(d => d[keyBurnout] ?? 0)

  const cx = i => padLeft + (i / (data.length - 1)) * (W - padLeft - padRight)
  const cy = v => padTop  + (1 - v / 100) * (H - padTop - padBottom)

  const linePath = vals =>
    vals.map((v, i) => `${i === 0 ? "M" : "L"}${cx(i).toFixed(1)},${cy(v).toFixed(1)}`).join(" ")

  const areaPath = vals => {
    const line = linePath(vals)
    const last = vals.length - 1
    return `${line} L${cx(last).toFixed(1)},${cy(0).toFixed(1)} L${cx(0).toFixed(1)},${cy(0).toFixed(1)} Z`
  }

  const yTicks = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
  const xCount = Math.min(6, data.length)
  const xIdxs  = Array.from({ length: xCount }, (_, i) =>
    Math.round(i * (data.length - 1) / (xCount - 1))
  )
  const gridColor  = "rgba(128,128,120,0.12)"
  const gridStrong = "rgba(128,128,120,0.22)"
  const labelColor = "#9e9b94"

  const handleMouseMove = e => {
    const svg = svgRef.current
    if (!svg) return
    const rect = svg.getBoundingClientRect()
    const scaleX = W / rect.width
    const mouseX = (e.clientX - rect.left) * scaleX
    const ratio  = Math.max(0, Math.min(1, (mouseX - padLeft) / (W - padLeft - padRight)))
    setHover(Math.round(ratio * (data.length - 1)))
  }

  const hx = hover !== null ? cx(hover) : null

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`}
        style={{ width: "100%", height: "100%", cursor: "crosshair" }}
        preserveAspectRatio="xMidYMid meet"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <linearGradient id="gp" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1D9E75" stopOpacity="0.22" />
            <stop offset="100%" stopColor="#1D9E75" stopOpacity="0" />
          </linearGradient>
          <linearGradient id="gb" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#D85A30" stopOpacity="0.18" />
            <stop offset="100%" stopColor="#D85A30" stopOpacity="0" />
          </linearGradient>
        </defs>

        {/* Gridlines */}
        {yTicks.map(tick => (
          <g key={tick}>
            <line x1={padLeft} y1={cy(tick)} x2={W - padRight} y2={cy(tick)}
              stroke={tick % 25 === 0 ? gridStrong : gridColor}
              strokeWidth={tick % 25 === 0 ? "0.75" : "0.5"}
              strokeDasharray={tick % 25 === 0 ? "none" : "2 4"} />
            <text x={padLeft - 7} y={cy(tick)} fontSize="9" fill={labelColor}
              textAnchor="end" dominantBaseline="central" fontFamily="DM Sans,sans-serif">{tick}</text>
          </g>
        ))}

        {/* X labels */}
        {xIdxs.map(i => (
          <text key={i} x={cx(i)} y={H - 6} fontSize="9" fill={labelColor}
            textAnchor="middle" fontFamily="DM Sans,sans-serif">
            {data[i]?.date?.slice(5)}
          </text>
        ))}

        <line x1={padLeft} y1={padTop} x2={padLeft} y2={H - padBottom} stroke={gridStrong} strokeWidth="0.75" />

        {/* Areas */}
        <path d={areaPath(perfVals)}    fill="url(#gp)" />
        <path d={areaPath(burnoutVals)} fill="url(#gb)" />

        {/* Lines */}
        <path d={linePath(perfVals)}    fill="none" stroke="#1D9E75" strokeWidth="2" strokeLinejoin="round" />
        <path d={linePath(burnoutVals)} fill="none" stroke="#D85A30" strokeWidth="2" strokeLinejoin="round" />

        {/* Legend — TOP RIGHT inside chart */}
        <rect x={W - padRight - 146} y={padTop - 22} width={142} height={20} rx="4"
          fill="var(--surface)" fillOpacity="0.85" />
        <circle cx={W - padRight - 136} cy={padTop - 12} r="4" fill="#1D9E75" />
        <text x={W - padRight - 129} y={padTop - 12} fontSize="9" fill="#1D9E75"
          dominantBaseline="central" fontFamily="DM Sans,sans-serif">performance</text>
        <circle cx={W - padRight - 60} cy={padTop - 12} r="4" fill="#D85A30" />
        <text x={W - padRight - 53} y={padTop - 12} fontSize="9" fill="#D85A30"
          dominantBaseline="central" fontFamily="DM Sans,sans-serif">burnout risk</text>

        {/* Hover */}
        {hover !== null && (
          <>
            <line x1={hx} y1={padTop} x2={hx} y2={H - padBottom}
              stroke="rgba(128,128,120,0.35)" strokeWidth="1" strokeDasharray="3 3" />
            <circle cx={hx} cy={cy(perfVals[hover])}    r="4.5" fill="#1D9E75" stroke="var(--surface)" strokeWidth="1.5" />
            <circle cx={hx} cy={cy(burnoutVals[hover])} r="4.5" fill="#D85A30" stroke="var(--surface)" strokeWidth="1.5" />
          </>
        )}

        {/* End dots (no hover) */}
        {hover === null && (
          <>
            <circle cx={cx(data.length-1)} cy={cy(perfVals[perfVals.length-1])}       r="3.5" fill="#1D9E75" />
            <circle cx={cx(data.length-1)} cy={cy(burnoutVals[burnoutVals.length-1])} r="3.5" fill="#D85A30" />
          </>
        )}
      </svg>

      {/* Hover tooltip */}
      {hover !== null && (
        <div style={{ position: "absolute", top: 8, left: 52, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "8px 12px", fontSize: 12, pointerEvents: "none", minWidth: 140 }}>
          <div style={{ fontSize: 11, color: "var(--faint)", marginBottom: 5 }}>{data[hover]?.date}</div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 3 }}>
            <span style={{ color: "var(--muted)" }}>Performance</span>
            <span style={{ fontWeight: 500, color: "#1D9E75" }}>{perfVals[hover].toFixed(1)}</span>
          </div>
          <div style={{ display: "flex", justifyContent: "space-between", gap: 16 }}>
            <span style={{ color: "var(--muted)" }}>Burnout</span>
            <span style={{ fontWeight: 500, color: "#D85A30" }}>{burnoutVals[hover].toFixed(1)}</span>
          </div>
        </div>
      )}
    </div>
  )
}

function ProgressBar({ value, color }) {
  return (
    <div style={{ height: 5, background: "var(--border)", borderRadius: 99, overflow: "hidden" }}>
      <div style={{ height: "100%", width: `${Math.min(100, value)}%`, background: color, borderRadius: 99, transition: "width 0.8s ease" }} />
    </div>
  )
}

function insightText(profile) {
  if (!profile || Object.keys(profile).length === 0) return null
  const entries = Object.entries(profile).sort((a, b) => b[1] - a[1])
  const top = entries[0]?.[0]?.replace("_importance", "").replace("_", " ")
  return top ? `Your model weights ${top} most heavily. Keep that in mind on tough days.` : null
}

function badgeClass(metric, value) {
  if (metric === "burnout") return value < 40 ? "badge-green" : value < 65 ? "badge-amber" : "badge-red"
  if (metric === "perf")    return value > 65 ? "badge-green" : value > 45 ? "badge-amber" : "badge-red"
  if (metric === "sleep")   return value >= 7 ? "badge-green" : value >= 6 ? "badge-amber" : "badge-red"
  return "badge-green"
}

export default function Dashboard({ username, onNavigate }) {
  const [data,     setData]     = useState(null)
  const [tasks,    setTasks]    = useState([])
  const [progress, setProgress] = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`${API}/users/${username}/analysis`)
      .then(r => { if (!r.ok) return r.json().then(e => Promise.reject(e.detail)); return r.json() })
      .then(d => {
        setData(d)
        return fetch(`${API}/tasks/${username}?recommended_hours=${d.optimal_plan?.study ?? 3.5}`)
      })
      .then(r => r.json())
      .then(t => { setTasks(t.tasks || []); setProgress(t.progress || null); setLoading(false) })
      .catch(e => { setError(String(e)); setLoading(false) })
  }, [username])

  if (loading) return <div className="loading">Loading your data…</div>
  if (error) return (
    <div className="empty-state">
      <p>{error === "Not enough data yet" ? "Keep logging — you need at least a few entries before your dashboard unlocks." : `Could not load data: ${error}`}</p>
      <button className="btn-primary" onClick={() => onNavigate("log")}>Log an entry</button>
    </div>
  )

  const { latest, baselines, optimal_plan, chart_data, profile } = data
  const hour     = new Date().getHours()
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening"
  const today    = new Date().toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })
  const pct      = progress?.progress_pct ?? 0
  const barColor = pct >= 100 ? "var(--green)" : pct >= 50 ? "var(--blue)" : "var(--amber)"

  const recItems = optimal_plan ? [
    { label: "Sleep",    value: optimal_plan.sleep,    color: "var(--blue)",   max: 12, icon: "😴", desc: "hours of sleep" },
    { label: "Study",    value: optimal_plan.study,    color: "var(--green)",  max: 8,  icon: "📚", desc: "hours of study" },
    { label: "Training", value: optimal_plan.training, color: "var(--purple)", max: 4,  icon: "🏋️", desc: "hours of training" },
  ] : []

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, height: "100%" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontSize: 16, fontWeight: 500, color: "var(--text)" }}>{greeting}, {username}</h1>
          <p style={{ fontSize: 12, color: "var(--faint)", marginTop: 2 }}>Here's how you're doing</p>
        </div>
        <span style={{ fontSize: 12, color: "var(--faint)", background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", padding: "5px 10px" }}>{today}</span>
      </div>

      {/* Metric cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0,1fr))", gap: 10 }}>
        {[
          { label: "Performance score", value: latest.performance_score, sub: "out of 100",                      badge: badgeClass("perf",    latest.performance_score), badgeText: latest.performance_score > 65 ? "on track" : latest.performance_score > 45 ? "moderate" : "needs attention" },
          { label: "Burnout risk",       value: latest.burnout_risk,      sub: "out of 100",                      badge: badgeClass("burnout", latest.burnout_risk),       badgeText: latest.burnout_risk < 40 ? "low" : latest.burnout_risk < 65 ? "moderate" : "high" },
          { label: "Avg sleep (7d)",     value: latest.avg_sleep_7, unit:"h", sub: `optimal: ${baselines.optimal_sleep}h`, badge: badgeClass("sleep", latest.avg_sleep_7), badgeText: latest.avg_sleep_7 >= 7 ? "good" : latest.avg_sleep_7 >= 6 ? "slightly low" : "low" },
          { label: "Avg workload (7d)",  value: latest.avg_load,    unit:"h", sub: `optimal: ${baselines.optimal_load}h`,  badge: latest.avg_load <= baselines.optimal_load + 0.5 ? "badge-green" : "badge-amber", badgeText: latest.avg_load <= baselines.optimal_load + 0.5 ? "on track" : "above baseline" },
        ].map(m => (
          <div key={m.label} style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "14px 16px" }}>
            <div style={{ fontSize: 11, color: "var(--faint)", marginBottom: 5 }}>{m.label}</div>
            <div style={{ fontSize: 24, fontWeight: 500, color: "var(--text)", lineHeight: 1 }}>
              {m.value}{m.unit && <span style={{ fontSize: 13, fontWeight: 400, color: "var(--faint)" }}>{m.unit}</span>}
            </div>
            <div style={{ fontSize: 11, color: "var(--faint)", marginTop: 3 }}>{m.sub}</div>
            <div className={`badge ${m.badge}`}>{m.badgeText}</div>
          </div>
        ))}
      </div>

      {/* Charts + Recommendation row */}
      <div style={{ display: "grid", gridTemplateColumns: "3fr 2fr", gap: 10 }}>
        {/* Chart */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem", display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)", marginBottom: "0.75rem" }}>
            Performance & burnout — last {chart_data.length} days
          </div>
          <div style={{ flex: 1, minHeight: 240 }}>
            <Sparkline data={chart_data} keyPerf="performance_score" keyBurnout="burnout_risk" />
          </div>
        </div>

        {/* Recommendation */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem", display: "flex", flexDirection: "column", gap: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)", marginBottom: "1rem" }}>Tomorrow's recommendation</div>
          {optimal_plan ? (
            <>
              {/* Three big rec items */}
              <div style={{ display: "flex", flexDirection: "column", gap: 8, flex: 1 }}>
                {recItems.map(r => (
                  <div key={r.label} style={{ flex: 1, background: "var(--bg)", borderRadius: "var(--radius-md)", padding: "14px 16px", display: "flex", flexDirection: "column", justifyContent: "space-between", gap: 8 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <span style={{ fontSize: 16 }}>{r.icon}</span>
                        <span style={{ fontSize: 12, color: "var(--muted)" }}>{r.label}</span>
                      </div>
                      <span style={{ fontSize: 26, fontWeight: 500, color: "var(--text)", lineHeight: 1 }}>
                        {r.value}<span style={{ fontSize: 12, color: "var(--faint)", fontWeight: 400 }}>h</span>
                      </span>
                    </div>
                    <div style={{ height: 4, background: "var(--border)", borderRadius: 99, overflow: "hidden" }}>
                      <div style={{ height: "100%", width: `${(r.value / r.max) * 100}%`, background: r.color, borderRadius: 99 }} />
                    </div>
                    <div style={{ fontSize: 10, color: "var(--faint)" }}>{r.desc} recommended</div>
                  </div>
                ))}
              </div>

              {/* Predicted outcomes */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 8 }}>
                <div style={{ background: "var(--green-bg)", borderRadius: "var(--radius-md)", padding: "12px 14px", textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: "var(--green-txt)", marginBottom: 3 }}>predicted performance</div>
                  <div style={{ fontSize: 26, fontWeight: 500, color: "var(--green-txt)", lineHeight: 1 }}>{optimal_plan.pred_perf}</div>
                  <div style={{ fontSize: 10, color: "var(--green-txt)", opacity: 0.7, marginTop: 2 }}>out of 100</div>
                </div>
                <div style={{ background: "var(--red-bg)", borderRadius: "var(--radius-md)", padding: "12px 14px", textAlign: "center" }}>
                  <div style={{ fontSize: 10, color: "var(--red-txt)", marginBottom: 3 }}>predicted burnout</div>
                  <div style={{ fontSize: 26, fontWeight: 500, color: "var(--red-txt)", lineHeight: 1 }}>{optimal_plan.pred_burnout}</div>
                  <div style={{ fontSize: 10, color: "var(--red-txt)", opacity: 0.7, marginTop: 2 }}>out of 100</div>
                </div>
              </div>
            </>
          ) : (
            <p style={{ fontSize: 12, color: "var(--faint)" }}>Log more entries to unlock recommendations.</p>
          )}
        </div>
      </div>

      {/* Bottom row */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        {/* Baselines */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem" }}>
          <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text)", marginBottom: "1rem" }}>Personal baselines</div>
          {[
            { label: "optimal sleep",      val: `${baselines.optimal_sleep} h`,        pct: (baselines.optimal_sleep / 12) * 100, color: "var(--blue)"   },
            { label: "optimal study load", val: `${baselines.optimal_load} h`,         pct: (baselines.optimal_load / 8)  * 100, color: "var(--purple)" },
            { label: "baseline stress",    val: `${baselines.baseline_stress} / 10`,   pct: baselines.baseline_stress * 10,       color: "var(--amber)"  },
            { label: "baseline fatigue",   val: `${baselines.baseline_fatigue} / 10`,  pct: baselines.baseline_fatigue * 10,      color: "var(--red)"    },
          ].map(b => (
            <div key={b.label} style={{ marginBottom: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--muted)", marginBottom: 5 }}>
                <span>{b.label}</span><span>{b.val}</span>
              </div>
              <ProgressBar value={b.pct} color={b.color} />
            </div>
          ))}
          {insightText(profile) && (
            <div style={{ background: "var(--bg)", borderRadius: "var(--radius-sm)", padding: "10px 12px", marginTop: 10 }}>
              <div style={{ fontSize: 11, color: "var(--faint)", marginBottom: 2 }}>model insight</div>
              <div style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.5 }}>{insightText(profile)}</div>
            </div>
          )}
        </div>

        {/* Tasks */}
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "1.25rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
            <span style={{ fontSize: 13, fontWeight: 500, color: "var(--text)" }}>Today's tasks</span>
            <button onClick={() => onNavigate("tasks")} style={{ background: "none", border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", fontSize: 11, padding: "4px 10px", cursor: "pointer", color: "var(--muted)", fontFamily: "inherit" }}>manage →</button>
          </div>

          {progress && (
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "var(--muted)", marginBottom: 5 }}>
                <span>{progress.completed_hours}h completed</span>
                <span style={{ color: pct >= 100 ? "var(--green-txt)" : "var(--faint)" }}>
                  {pct >= 100 ? "Goal reached!" : `${pct.toFixed(0)}% of ${progress.recommended}h goal`}
                </span>
              </div>
              <div style={{ height: 6, background: "var(--border)", borderRadius: 99, overflow: "hidden" }}>
                <div style={{ height: "100%", width: `${pct}%`, background: barColor, borderRadius: 99, transition: "width 0.8s ease" }} />
              </div>
            </div>
          )}

          {tasks.length === 0 ? (
            <div style={{ fontSize: 12, color: "var(--faint)", padding: "8px 0" }}>
              No tasks yet.{" "}
              <button onClick={() => onNavigate("tasks")} style={{ background: "none", border: "none", color: "var(--blue-txt)", cursor: "pointer", fontSize: 12, padding: 0, fontFamily: "inherit" }}>Add one →</button>
            </div>
          ) : (
            tasks.slice(0, 6).map(task => (
              <div key={task.id} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
                <div style={{ width: 14, height: 14, borderRadius: 4, border: task.completed ? "none" : "1px solid var(--border-md)", background: task.completed ? "var(--green)" : "transparent", flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  {task.completed && <div style={{ width: 5, height: 3, borderLeft: "1.5px solid white", borderBottom: "1.5px solid white", transform: "rotate(-45deg) translateY(-1px)" }} />}
                </div>
                <span style={{ fontSize: 13, color: task.completed ? "var(--faint)" : "var(--text)", flex: 1, textDecoration: task.completed ? "line-through" : "none" }}>{task.name}</span>
                <span style={{ fontSize: 11, color: "var(--faint)" }}>{task.hours}h</span>
              </div>
            ))
          )}
          {tasks.length > 6 && (
            <p style={{ fontSize: 11, color: "var(--faint)", marginTop: 8 }}>
              +{tasks.length - 6} more — <button onClick={() => onNavigate("tasks")} style={{ background: "none", border: "none", color: "var(--blue-txt)", cursor: "pointer", fontSize: 11, padding: 0, fontFamily: "inherit" }}>view all</button>
            </p>
          )}
        </div>
      </div>
    </div>
  )
}