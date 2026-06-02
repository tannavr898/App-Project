import { useEffect, useState } from "react"
import { apiFetch, getCachedJson } from "../api"
import "../styles/Companion.css"

const companionMemory = new Map()

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))
const toNumber = (value) => {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const trendLabel = (trend) => {
  if (!trend) return "Stable"
  const normalized = String(trend).toLowerCase()
  if (normalized === "improving" || normalized === "rising" || normalized === "improved") return "Improving"
  if (normalized === "declining" || normalized === "falling" || normalized === "worsening") return "Declining"
  return "Stable"
}

const trendTone = (trend) => {
  if (!trend) return "neutral"
  const normalized = String(trend).toLowerCase()
  if (normalized === "improving" || normalized === "rising" || normalized === "improved") return "good"
  if (normalized === "declining" || normalized === "falling" || normalized === "worsening") return "bad"
  return "neutral"
}

const xpEventLabel = (eventName) => {
  const labels = {
    first_entry: "First log",
    daily_entry: "Daily log",
    milestone_day_3: "3-day streak",
    milestone_day_7: "7-day streak",
    milestone_day_14: "14-day streak",
    milestone_day_30: "30-day streak",
    consistency_21: "21 entries",
    tasks_completed: "Tasks completed",
    full_task_day: "Full task day",
  }
  return labels[eventName] || String(eventName || "XP event").replace(/_/g, " ")
}

const LEVEL_NAMES = [
  "Seed",
  "Sprout",
  "Bud",
  "Flower",
  "Tree",
  "Small woods",
  "Forest pond",
  "Forest lake",
  "River",
  "Amazon rainforest",
]

const LEVEL_THEMES = [
  { background: "#F5EFE0", surface: "#FBF6EC", border: "#C8B89A", accent: "#8B6914", ink: "#3D2E08", muted: "#A07820" },
  { background: "#EDF7DC", surface: "#F3FCE8", border: "#A3C46A", accent: "#5E8C2A", ink: "#2A4A10", muted: "#6B9A30" },
  { background: "#FEF0F5", surface: "#FFF5F8", border: "#F4A8C0", accent: "#C04478", ink: "#7A1540", muted: "#D4527E" },
  { background: "#FFF7ED", surface: "#FFFBF5", border: "#FDBA74", accent: "#C2620A", ink: "#7A3A00", muted: "#D97706" },
  { background: "#EBF5DB", surface: "#F0F8E6", border: "#6B9A30", accent: "#3A6A10", ink: "#1A4000", muted: "#5A8A20" },
  { background: "#E0F0D0", surface: "#EAF5DA", border: "#4A7A3A", accent: "#2A5A10", ink: "#183008", muted: "#3E7018" },
  { background: "#D5EEF5", surface: "#E5F5F8", border: "#2A8A8A", accent: "#1A6A7A", ink: "#0A3A48", muted: "#2A8A9A" },
  { background: "#C8E8F8", surface: "#E0F0FA", border: "#1A6AB0", accent: "#1A5A9A", ink: "#0A2A58", muted: "#2A7AC0" },
  { background: "#B8D8F0", surface: "#D8EEF8", border: "#0E5A8A", accent: "#0A4878", ink: "#051838", muted: "#1A6898" },
  { background: "#0A2010", surface: "#0E2A14", border: "#0A4020", accent: "#40B860", ink: "#B8F0C8", muted: "#60D080" },
]

const levelNameForLevel = (level) => LEVEL_NAMES[clamp(Math.round(level || 1), 1, LEVEL_NAMES.length) - 1]
const levelThemeForLevel = (level) => LEVEL_THEMES[clamp(Math.round(level || 1), 1, LEVEL_THEMES.length) - 1]
const levelLadderText = LEVEL_NAMES.join(" → ")

function StatChip({ label, value }) {
  return (
    <div className="companion-chip">
      <span className="companion-chip-label">{label}</span>
      <span className="companion-chip-value">{value}</span>
    </div>
  )
}

function HelpIcon({ text }) {
  return (
    <button className="companion-help" type="button" title={text} aria-label={text}>
      ?
    </button>
  )
}

function SectionTitle({ label, help }) {
  return (
    <div className="companion-section-title">
      <span>{label}</span>
      <HelpIcon text={help} />
    </div>
  )
}

function sceneClassForLevel(level) {
  if (level <= 1) return "scene-seed"
  if (level === 2) return "scene-sprout"
  if (level === 3) return "scene-bud"
  if (level === 4) return "scene-flower"
  if (level === 5) return "scene-tree"
  if (level === 6) return "scene-woods"
  if (level === 7) return "scene-pond"
  if (level === 8) return "scene-lake"
  if (level === 9) return "scene-river"
  return "scene-rainforest"
}

export default function Companion({ username, variant = "full", onNavigate }) {
  const cacheKey = `companion:${username}`
  const cachedCompanion = companionMemory.get(username) || getCachedJson(cacheKey, 300000)

  const [companion, setCompanion] = useState(cachedCompanion)
  const [loading, setLoading] = useState(!cachedCompanion)
  const [error, setError] = useState(null)
  const [pollingEnabled, setPollingEnabled] = useState(true)

  const isSummary = variant === "summary"

  const fetchCompanion = async () => {
    try {
      if (!pollingEnabled) return
      setError(null)
      const response = await apiFetch(`/companion/${username}/summary`, {
        timeoutMs: 20000,
        cacheKey,
        cacheTtlMs: 300000,
      })

      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          setPollingEnabled(false)
        }
        throw new Error(`Failed to fetch companion: ${response.statusText}`)
      }

      const data = await response.json()
      companionMemory.set(username, data)
      setCompanion(data)
    } catch (err) {
      console.error("Companion fetch error:", err)
      if (!companion) {
        const message = err?.name === "AbortError"
          ? "Companion is taking longer than expected"
          : (err?.message || "Failed to load companion")
        setError(message)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setPollingEnabled(true)
    setLoading(!cachedCompanion)
    fetchCompanion()
  }, [username])

  useEffect(() => {
    if (!pollingEnabled) return
    const interval = setInterval(() => {
      fetchCompanion()
    }, 60000)
    return () => clearInterval(interval)
  }, [username, pollingEnabled])

  useEffect(() => {
    const handleTasksUpdated = event => {
      if (event?.detail?.username && event.detail.username !== username) return
      fetchCompanion()
    }
    window.addEventListener("pulse:tasks-updated", handleTasksUpdated)
    return () => window.removeEventListener("pulse:tasks-updated", handleTasksUpdated)
  }, [username, pollingEnabled])

  if (loading) {
    return (
      <div className={`companion-container ${isSummary ? "is-summary" : "is-full"} loading`}>
        <div className="spinner" />
        <p>{isSummary ? "Loading companion summary..." : "Growing your companion..."}</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`companion-container ${isSummary ? "is-summary" : "is-full"} error`}>
        <p>Could not load companion</p>
      </div>
    )
  }

  if (!companion) return null

  const {
    level,
    level_name,
    xp_current,
    xp_to_level_up,
    level_progress_pct,
    mood_trend,
    mood_emoji,
    streak,
    days_since_activity,
    performance_influence,
    comeback_available,
    comeback_bonus_xp,
    xp_breakdown = {},
    recent_xp_events = [],
  } = companion

  const performanceScore = clamp(toNumber(performance_influence?.current_performance), 0, 100)
  const burnoutScore = clamp(toNumber(performance_influence?.current_burnout), 0, 100)
  const xpProgress = clamp(toNumber(level_progress_pct), 0, 100)
  const hasNextLevel = xp_to_level_up > 0
  const xpLabel = hasNextLevel ? `${xp_current} / ${xp_current + xp_to_level_up} XP` : `${xp_current} XP`
  const xpHelper = hasNextLevel ? `${xp_to_level_up} XP to next level` : "Max level reached"
  const moodLabel = String(mood_trend || "steady").replace(/_/g, " ")
  const daysAwayLabel = days_since_activity > 0 ? `${days_since_activity}d away` : "active today"
  const trend = performance_influence?.trend
  const trendText = trendLabel(trend)
  const trendClass = trendTone(trend)
  const sceneClass = sceneClassForLevel(level)
  const levelName = level_name || levelNameForLevel(level)
  const nextLevelName = hasNextLevel ? levelNameForLevel(level + 1) : null
  const levelTheme = levelThemeForLevel(level)
  const levelStyle = {
    "--companion-level-background": levelTheme.background,
    "--companion-level-surface": levelTheme.surface,
    "--companion-level-border": levelTheme.border,
    "--companion-level-accent": levelTheme.accent,
    "--companion-level-ink": levelTheme.ink,
    "--companion-level-muted": levelTheme.muted,
  }
  const levelInsight = hasNextLevel
    ? `${levelName} sits on level ${clamp(Math.round(level || 1), 1, 10)} of 10. Keep logging daily to grow toward ${nextLevelName}.`
    : `${levelName} has reached the top of the ladder. Keep your streak steady so the ecosystem stays balanced.`
  const levelLadderInsight = `Level ladder: ${levelLadderText}`
  const xpBreakdownRows = [
    { label: "Entries", value: xp_breakdown.entries || 0 },
    { label: "Tasks", value: xp_breakdown.tasks || 0 },
    { label: "Milestones", value: xp_breakdown.milestones || 0 },
    { label: "Bonus", value: xp_breakdown.variable || 0 },
  ]

  const pulseMode = burnoutScore >= 65 && performanceScore <= 45
    ? "low"
    : (burnoutScore <= 35 && performanceScore >= 70 ? "perfect" : "medium")

  const trendImpactText = `Performance ${performanceScore.toFixed(0)}/100, burnout ${burnoutScore.toFixed(0)}/100`
  const pulseModeLabel = pulseMode === "low"
    ? "erratic"
    : (pulseMode === "perfect" ? "smooth long waves" : "steady with jumps")

  const renderStageArt = () => (
    <div className={`companion-art companion-art--${pulseMode} companion-art--${sceneClass}`}>
      <span className="companion-art-orbit companion-art-orbit--a" />
      <span className="companion-art-orbit companion-art-orbit--b" />
      <span className={`companion-energy companion-energy--${trendClass} companion-energy--${pulseMode}`} />
      <span className="companion-sky companion-sky--sun" />
      <span className="companion-cloud companion-cloud--1" />
      <span className="companion-cloud companion-cloud--2" />
      <span className="companion-river companion-river--main" />
      <span className="companion-river companion-river--shine" />
      <span className="companion-ripple companion-ripple--1" />
      <span className="companion-ripple companion-ripple--2" />
      <span className="companion-canopy companion-canopy--left" />
      <span className="companion-canopy companion-canopy--right" />
      <span className="companion-art-petal companion-art-petal--1" />
      <span className="companion-art-petal companion-art-petal--2" />
      <span className="companion-art-petal companion-art-petal--3" />
      <span className={`companion-art-core ${sceneClass}`}>
        <span className="companion-scene-ground" />
        <span className="companion-scene-tree companion-scene-tree--1" />
        <span className="companion-scene-tree companion-scene-tree--2" />
        <span className="companion-scene-tree companion-scene-tree--3" />
        <span className="companion-scene-water" />
        <span className="companion-scene-bloom companion-scene-bloom--1" />
        <span className="companion-scene-bloom companion-scene-bloom--2" />
      </span>
      <span className="companion-art-spark companion-art-spark--1" />
      <span className="companion-art-spark companion-art-spark--2" />
      <span className="companion-art-spark companion-art-spark--3" />
      <span className="companion-leaf companion-leaf--1" />
      <span className="companion-leaf companion-leaf--2" />
      <span className="companion-leaf companion-leaf--3" />
    </div>
  )

  if (isSummary) {
    return (
      <div className="companion-container companion-shell companion-shell--summary companion-summary-dominant">
        <div className="companion-level-card companion-level-card--summary" style={levelStyle}>
          <div className="companion-level-card__top">
            <div className="companion-level-card__title-group">
              <div className="companion-level-badge">LEVEL {level}</div>
              <div className="companion-level-name">{levelName}</div>
              <div className="companion-level-subtitle">{mood_emoji} {moodLabel}</div>
            </div>
            <div className="companion-level-pts">{xpLabel}</div>
          </div>
          <div className="companion-stage companion-stage--summary-dominant" style={levelStyle}>
            <div className="companion-stage-glow" />
            {renderStageArt()}
            {onNavigate && (
              <button className="companion-button companion-button--ghost companion-open-fab" onClick={() => onNavigate("companion")}>
                Open
              </button>
            )}
          </div>
          <div className="companion-level-card__bottom">
            <span>{levelInsight}</span>
            <span>{levelLadderInsight}</span>
          </div>
        </div>
        <div className="companion-progress-block companion-progress-block--summary-dominant">
          <div className="xp-bar-container">
            <div className="xp-bar-fill" style={{ width: `${xpProgress}%` }} />
          </div>
          <div className="companion-progress-foot">
            <span>{xpLabel}</span>
            <span>{xpHelper}</span>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="companion-container companion-shell companion-shell--full">
      <div className="companion-full-layout">
        <div className="companion-stage companion-stage--full companion-stage--full-left" style={levelStyle}>
          <div className="companion-stage-glow" />
          {renderStageArt()}
        </div>

        <div className="companion-full-content">
          <div className="companion-hero">
            <div className="companion-copy companion-copy--full">
              <div className="companion-kicker">
                Pulse companion
                <HelpIcon text="This companion is a living summary of your streak, recovery, performance, and burnout trends." />
              </div>
              <div className="companion-level-card companion-level-card--inline" style={levelStyle}>
                <div className="companion-level-card__top">
                  <div className="companion-level-card__title-group">
                    <div className="companion-level-badge">LEVEL {level}</div>
                    <div className="companion-level-name">{levelName}</div>
                    <div className="companion-level-subtitle">{mood_emoji} {moodLabel}</div>
                  </div>
                  <div className="companion-level-pts">{xpLabel}</div>
                </div>
                <div className="companion-level-card__bottom">
                  <span>{levelInsight}</span>
                  <span>{levelLadderInsight}</span>
                </div>
              </div>

              <div className="companion-summary-grid">
                <StatChip label="Streak" value={`${streak} days`} />
                <StatChip label="Status" value={daysAwayLabel} />
                <StatChip label="Trend" value={trendText} />
              </div>

              <div className="companion-actions">
                {onNavigate && (
                  <button className="companion-button" onClick={() => onNavigate("dashboard")}>
                    Back to overview
                  </button>
                )}
                <div className={`companion-trend companion-trend--${trendClass}`}>
                  <span>Trend: {trendText}</span>
                  <HelpIcon text="Trend reflects whether your recent performance has been moving up, staying steady, or slipping." />
                </div>
              </div>

              {comeback_available && (
                <div className="comeback-badge comeback-badge--wide">Return bonus: +{comeback_bonus_xp} XP</div>
              )}

              <div className="companion-dialogue companion-dialogue--compact">
                Keep logging daily. This ecosystem expands and smooths out as performance rises and burnout stays in check.
              </div>
            </div>
          </div>

          <div className="companion-grid">
            <div className="companion-column">
              <div className="companion-panel">
                <SectionTitle
                  label="Level progress"
                  help="The companion advances through levels as XP accumulates. Each level contains multiple visual stages."
                />
                <div className="companion-xp-row">
                  <span>{xpLabel}</span>
                  <span>{xpHelper}</span>
                </div>
                <div className="xp-bar-container xp-bar-container--large">
                  <div className="xp-bar-fill" style={{ width: `${xpProgress}%` }} />
                </div>
                <div className="companion-xp-breakdown">
                  {xpBreakdownRows.map(row => (
                    <div key={row.label}>
                      <span>{row.label}</span>
                      <strong>{row.value} XP</strong>
                    </div>
                  ))}
                </div>
              </div>

              <div className="companion-panel">
                <SectionTitle
                  label="Trend impact"
                  help="Your trend is driven by recent score movement. Better performance with lower burnout creates smoother, stronger pulse behavior."
                />
                <div className={`companion-trend companion-trend--${trendClass}`}>
                  <span>Trend: {trendText}</span>
                  <HelpIcon text="Trend is computed from the recent performance trend, not just today's entry." />
                </div>
                <div className="companion-trend-impact-copy">{trendImpactText}</div>
                <div className="companion-trend-impact-copy">Pulse behavior: {pulseModeLabel}</div>
              </div>
            </div>

            <div className="companion-column">
              <div className="companion-panel companion-panel--soft">
                <SectionTitle
                  label="Daily snapshot"
                  help="This shows the current streak, recency of your last log, and how close you are to the next level."
                />
                <div className="companion-bullet-list">
                  <div>
                    <span>Current streak</span>
                    <strong>{streak} days</strong>
                  </div>
                  <div>
                    <span>Days since last entry</span>
                    <strong>{days_since_activity}</strong>
                  </div>
                  <div>
                    <span>Level progress</span>
                    <strong>{xpProgress.toFixed(0)}%</strong>
                  </div>
                  <div>
                    <span>Next level</span>
                    <strong>{hasNextLevel ? `${xp_to_level_up} XP away` : "Max level"}</strong>
                  </div>
                </div>
              </div>

              <div className="companion-panel companion-panel--soft">
                <SectionTitle
                  label="How it feels"
                  help="The companion mood reflects your recent trend and how your latest entry affected it."
                />
                <div className="companion-feeling">
                  <span className="companion-mood-emoji companion-mood-emoji--large">{mood_emoji}</span>
                  <div>
                    <strong>{moodLabel}</strong>
                    <p>A smoother pulse means your ecosystem is stabilizing.</p>
                  </div>
                </div>
              </div>

              <div className="companion-panel companion-panel--soft">
                <SectionTitle
                  label="Recent XP"
                  help="XP comes from daily logs, completed tasks, streak milestones, and deterministic daily bonuses."
                />
                {recent_xp_events.length > 0 ? (
                  <div className="companion-event-list">
                    {recent_xp_events.slice().reverse().map((event, index) => (
                      <div key={`${event.event}-${event.date}-${index}`}>
                        <span>{xpEventLabel(event.event)}</span>
                        <strong>+{event.xp} XP</strong>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="companion-empty-copy">Log an entry or complete tasks to start earning XP.</p>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
