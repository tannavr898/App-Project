import { useEffect, useState } from "react"
import { apiFetch } from "../api"
import "../styles/Companion.css"

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

function ScoreCard({ label, value, tone, helper, percent }) {
  return (
    <div className="companion-score-card">
      <div className="companion-score-head">
        <span className="companion-score-label">{label}</span>
        <span className={`companion-score-value tone-${tone}`}>{value}</span>
      </div>
      <div className="companion-meter">
        <div className={`companion-meter-fill tone-${tone}`} style={{ width: `${clamp(percent, 0, 100)}%` }} />
      </div>
      <div className="companion-score-helper">{helper}</div>
    </div>
  )
}

export default function Companion({ username, variant = "full", onNavigate }) {
  const [companion, setCompanion] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [pollingEnabled, setPollingEnabled] = useState(true)

  const isSummary = variant === "summary"

  const fetchCompanion = async () => {
    try {
      if (!pollingEnabled) return
      setError(null)
      const response = await apiFetch(`/companion/${username}/summary`, { timeoutMs: 20000 })
      if (!response.ok) {
        if (response.status === 401 || response.status === 403) {
          setPollingEnabled(false)
        }
        throw new Error(`Failed to fetch companion: ${response.statusText}`)
      }
      const data = await response.json()
      setCompanion(data)
    } catch (err) {
      console.error("Companion fetch error:", err)
      const message = err?.name === "AbortError"
        ? "Companion is taking longer than expected"
        : (err?.message || "Failed to load companion")
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setPollingEnabled(true)
    setLoading(true)
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
        <p>{isSummary ? "Loading companion summary…" : "Growing your companion…"}</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className={`companion-container ${isSummary ? "is-summary" : "is-full"} error`}>
        <p>⚠️ Could not load companion</p>
      </div>
    )
  }

  if (!companion) {
    return null
  }

  const {
    level,
    level_name,
    xp_current,
    xp_to_level_up,
    level_progress_pct,
    visual_stage,
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
  const xpLabel = hasNextLevel
    ? `${xp_current} / ${xp_current + xp_to_level_up} XP`
    : `${xp_current} XP`
  const xpHelper = hasNextLevel
    ? `${xp_to_level_up} XP to next level`
    : "Max level reached"
  const moodLabel = String(mood_trend || "steady").replace(/_/g, " ")
  const daysAwayLabel = days_since_activity > 0 ? `${days_since_activity}d away` : "active today"
  const trend = performance_influence?.trend
  const trendText = trendLabel(trend)
  const trendClass = trendTone(trend)

  if (isSummary) {
    return (
      <div className="companion-container companion-shell companion-shell--summary">
        <div className="companion-summary-header">
          <div className="companion-stage companion-stage--summary">
            <div className="companion-stage-glow" />
            <div className="companion-visual">{visual_stage}</div>
            <div className="heartbeat">💓</div>
          </div>

          <div className="companion-copy">
            <div className="companion-kicker">Companion</div>
            <h3>{level_name}</h3>
            <p>
              <span className="companion-mood-emoji">{mood_emoji}</span>
              <span>{moodLabel}</span>
              <span className="companion-dot">•</span>
              <span>Lv {level}</span>
            </p>
          </div>

          {onNavigate && (
            <button className="companion-button companion-button--ghost" onClick={() => onNavigate("companion")}>
              Open
            </button>
          )}
        </div>

        <div className="companion-summary-grid">
          <StatChip label="XP" value={xpLabel} />
          <StatChip label="Streak" value={`${streak} days`} />
          <StatChip label="Mood" value={trendText} />
        </div>

        <div className="companion-progress-block">
          <div className="companion-progress-head">
            <span>Progress</span>
            <span>{xpProgress.toFixed(0)}%</span>
          </div>
          <div className="xp-bar-container">
            <div className="xp-bar-fill" style={{ width: `${xpProgress}%` }} />
          </div>
          <div className="companion-progress-foot">
            <span>{xpHelper}</span>
            <span>{daysAwayLabel}</span>
          </div>
        </div>

        {comeback_available && (
          <div className="comeback-badge">🎯 Return bonus: +{comeback_bonus_xp} XP</div>
        )}
      </div>
    )
  }

  return (
    <div className="companion-container companion-shell companion-shell--full">
      <div className="companion-hero">
        <div className="companion-stage companion-stage--full">
          <div className="companion-stage-glow" />
          <div className="companion-visual">{visual_stage}</div>
          <div className="heartbeat">💓</div>
        </div>

        <div className="companion-copy companion-copy--full">
          <div className="companion-kicker">Pulse companion</div>
          <h2>{level_name}</h2>
          <p>
            {mood_emoji} {moodLabel} · level {level}
          </p>

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
              {trendText}
            </div>
          </div>
        </div>

        <div className="companion-hero-side">
          {comeback_available && (
            <div className="comeback-badge comeback-badge--wide">🎯 Return bonus: +{comeback_bonus_xp} XP</div>
          )}
          <div className="companion-dialogue companion-dialogue--compact">
            Keep logging daily. Your companion gets stronger with every check-in.
          </div>
        </div>
      </div>

      <div className="companion-grid">
        <div className="companion-column">
          <div className="companion-panel">
            <div className="companion-panel-title">Level progress</div>
            <div className="companion-xp-row">
              <span>{xpLabel}</span>
              <span>{xpHelper}</span>
            </div>
            <div className="xp-bar-container xp-bar-container--large">
              <div className="xp-bar-fill" style={{ width: `${xpProgress}%` }} />
            </div>
          </div>

          <div className="companion-panel">
            <div className="companion-panel-title">Your influence</div>
            <div className="companion-score-grid">
              <ScoreCard
                label="Performance"
                value={`${performanceScore.toFixed(0)}/100`}
                tone="performance"
                helper="Higher means the companion feels more energized."
                percent={performanceScore}
              />
              <ScoreCard
                label="Burnout"
                value={`${burnoutScore.toFixed(0)}/100`}
                tone="burnout"
                helper="Lower is better for recovery and growth."
                percent={burnoutScore}
              />
            </div>
            <div className={`companion-trend companion-trend--${trendClass}`}>Trend: {trendText}</div>
          </div>
        </div>

        <div className="companion-column">
          <div className="companion-panel companion-panel--soft">
            <div className="companion-panel-title">Daily snapshot</div>
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
            <div className="companion-panel-title">How it feels</div>
            <div className="companion-feeling">
              <span className="companion-mood-emoji companion-mood-emoji--large">{mood_emoji}</span>
              <div>
                <strong>{moodLabel}</strong>
                <p>Keep the streak alive and the plant stays lively.</p>
              </div>
            </div>
          </div>

          <div className="companion-dialogue">
            Keep logging daily! Your companion grows stronger with your commitment.
          </div>
        </div>
      </div>
    </div>
  )
}
