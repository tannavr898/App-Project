import React, { useState, useEffect } from "react";
import { apiFetch } from "../api";
import "../styles/Companion.css";

/**
 * Companion - Interactive plant companion that grows with daily logging
 * Features: XP progress, mood indicators, streak tracking, performance influence
 * Updates every 60s to reflect live progress
 */
export default function Companion({ username, onError }) {
  const [companion, setCompanion] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [pulseKey, setPulseKey] = useState(0); // Force re-render for heartbeat animation

  // Fetch companion summary from API
  const fetchCompanion = async () => {
    try {
      setError(null);
      const response = await apiFetch(`/companion/${username}/summary`, { timeoutMs: 20000 });
      if (!response.ok) {
        throw new Error(`Failed to fetch companion: ${response.statusText}`);
      }
      const data = await response.json();
      setCompanion(data);
      setLoading(false);
    } catch (err) {
      console.error("Companion fetch error:", err);
      const message = err?.name === "AbortError" ? "Companion is taking longer than expected" : (err?.message || "Failed to load companion");
      setError(message);
      if (onError) onError(err);
      setLoading(false);
    }
  };

  // Initial fetch
  useEffect(() => {
    fetchCompanion();
  }, [username]);

  // Refresh every 60s + occasional pulse animation trigger
  useEffect(() => {
    const interval = setInterval(() => {
      fetchCompanion();
      setPulseKey((prev) => prev + 1); // Trigger heartbeat animation
    }, 60000);
    return () => clearInterval(interval);
  }, [username]);

  if (loading) {
    return (
      <div className="companion-container loading">
        <div className="spinner"></div>
        <p>Growing your companion...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="companion-container error">
        <p>⚠️ Could not load companion</p>
      </div>
    );
  }

  if (!companion) {
    return null;
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
  } = companion;

  return (
    <div className="companion-container">
      {/* Plant + Heartbeat */}
      <div className="companion-plant" key={`pulse-${pulseKey}`}>
        <div className="plant-visual">
          {visual_stage}
        </div>
        <div className="heartbeat">💓</div>
      </div>

      {/* Mood + Status */}
      <div className="companion-status">
        <div className="mood-section">
          <span className="mood-emoji">{mood_emoji}</span>
          <span className="mood-label">{mood_trend}</span>
          {days_since_activity > 1 && (
            <span className="days-away">({days_since_activity}d away)</span>
          )}
        </div>
        {comeback_available && (
          <div className="comeback-badge">
            🎯 Return bonus: +{comeback_bonus_xp} XP
          </div>
        )}
      </div>

      {/* Level + XP Progress */}
      <div className="companion-progress">
        <div className="level-info">
          <span className="level-badge">Lv {level}</span>
          <span className="level-name">{level_name}</span>
        </div>

        <div className="xp-bar-container">
          <div
            className="xp-bar-fill"
            style={{ width: `${Math.min(level_progress_pct, 100)}%` }}
          >
            <span className="xp-text">
              {xp_current} / {xp_to_level_up} XP
            </span>
          </div>
        </div>
      </div>

      {/* Streak Badge */}
      <div className="companion-streak">
        <span className="streak-icon">🔥</span>
        <span className="streak-count">{streak}</span>
        <span className="streak-label">day streak</span>
      </div>

      {/* Performance Influence */}
      <div className="performance-card">
        <h4>Your influence on companion</h4>
        <div className="performance-grid">
          <div className="performance-item">
            <span className="perf-label">Performance</span>
            <div className="perf-bar">
              <div
                className="perf-fill performance"
                style={{
                  width: `${Math.min(
                    (performance_influence.current_performance * 100) / 10,
                    100
                  )}%`,
                }}
              ></div>
            </div>
            <span className="perf-value">
              {performance_influence.current_performance.toFixed(1)}/10
            </span>
          </div>
          <div className="performance-item">
            <span className="perf-label">Burnout</span>
            <div className="perf-bar">
              <div
                className="perf-fill burnout"
                style={{
                  width: `${Math.min(
                    (performance_influence.current_burnout * 100) / 10,
                    100
                  )}%`,
                }}
              ></div>
            </div>
            <span className="perf-value">
              {performance_influence.current_burnout.toFixed(1)}/10
            </span>
          </div>
        </div>
        <div className="trend-badge">
          {performance_influence.trend === "rising" && "📈 Improving"}
          {performance_influence.trend === "stable" && "➡️ Stable"}
          {performance_influence.trend === "declining" && "📉 Declining"}
        </div>
      </div>

      {/* Companion Dialogue */}
      <div className="companion-dialogue">
        <p>Keep logging daily! Your companion grows stronger with your commitment.</p>
      </div>
    </div>
  );
}
