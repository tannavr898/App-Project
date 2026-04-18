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
  if (level <= 2) return "scene-seed"
  if (level <= 4) return "scene-flower"
  if (level <= 6) return "scene-woods"
  if (level <= 8) return "scene-lake"
  if (level <= 9) return "scene-river"
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

  const pulseMode = burnoutScore >= 65 && performanceScore <= 45
    ? "low"
    : (burnoutScore <= 35 && performanceScore >= 70 ? "perfect" : "medium")

  const trendImpactText = `Performance ${performanceScore.toFixed(0)}/100, burnout ${burnoutScore.toFixed(0)}/100`
  const pulseModeLabel = pulseMode === "low"
    ? "erratic"
    : (pulseMode === "perfect" ? "smooth long waves" : "steady with jumps")

  const renderStageArt = () => (
    <div className={`companion-art companion-art--${pulseMode}`}>
      <span className="companion-art-orbit companion-art-orbit--a" />
      <span className="companion-art-orbit companion-art-orbit--b" />
      <span className={`companion-energy companion-energy--${trendClass} companion-energy--${pulseMode}`} />
      <span className="companion-art-petal companion-art-petal--1" />
      <span className="companion-art-petal companion-art-petal--2" />
      <span className="companion-art-petal companion-art-petal--3" />
      <span className="companion-art-petal companion-art-petal--4" />
      <span className="companion-art-petal companion-art-petal--5" />
      <span className="companion-art-petal companion-art-petal--6" />
      <span className={`companion-art-core ${sceneClass}`}>
        <span className="companion-scene-ground" />
        <span className="companion-scene-tree companion-scene-tree--1" />
        <span className="companion-scene-tree companion-scene-tree--2" />
        <span className="companion-scene-tree companion-scene-tree--3" />
        <span className="companion-scene-water" />
      </span>
      <span className="companion-art-spark companion-art-spark--1" />
      <span className="companion-art-spark companion-art-spark--2" />
    </div>
  )

  if (isSummary) {
    return (
      <div className="companion-container companion-shell companion-shell--summary companion-summary-dominant">
        <div className="companion-stage companion-stage--summary-dominant">
          <div className="companion-stage-glow" />
          {renderStageArt()}
          {onNavigate && (
            <button className="companion-button companion-button--ghost companion-open-fab" onClick={() => onNavigate("companion")}>
              Open
            </button>
          )}
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
        <div className="companion-stage companion-stage--full companion-stage--full-left">
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
              <h2>{level_name}</h2>
              <p>{mood_emoji} {moodLabel} · level {level}</p>

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
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
