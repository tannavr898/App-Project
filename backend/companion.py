"""
Pulse Companion: Retention-optimized growth, mood, and reward system.

Core mechanics:
- Frontloaded XP rewards (first entry +50, daily bonuses, weekly jackpots)
- Dual mood system (instant today-based + trend 7-day-based)
- Progressive visual stages within levels (every 1-2 days of logging)
- Comeback loop (supportive, not punishing)
- Variable rewards (pseudo-random for dopamine)

Integrated by api.py for entry submission, task completion, and companion summary queries.
"""

from datetime import datetime, date, timedelta
import pandas as pd
import hashlib

try:
    from .data_store import (
        get_entries_dataframe,
        get_completion_history,
        get_todays_tasks,
        get_entry_row,
    )
except ImportError:
    from data_store import (
        get_entries_dataframe,
        get_completion_history,
        get_todays_tasks,
        get_entry_row,
    )


# ============================================================
# XP REWARDS (Retention-Optimized)
# ============================================================

# Entry XP (scales with streak day to incentivize daily habit)
def get_entry_xp(streak_day: int) -> int:
    """
    Bonus XP for logging an entry based on current streak length.
    Incentivizes daily habit formation.
    """
    if streak_day <= 3:
        return 10  # Days 1-3: baseline
    elif streak_day <= 7:
        return 12  # Days 4-7: +2 bonus
    elif streak_day <= 14:
        return 14  # Days 8-14: +4 bonus
    elif streak_day <= 30:
        return 16  # Days 15-30: +6 bonus
    else:
        return 18  # Days 31+: +8 bonus


# Variable XP luck (pseudo-random but deterministic per user/day)
def get_variable_xp_bonus(username: str, day: str) -> int:
    """
    Pseudo-random XP bonus to trigger variable reward dopamine.
    Deterministic (same user/day always gets same bonus) but unpredictable to user.
    
    Distribution: 70% +0, 20% +5, 10% +15
    """
    seed = f"{username}:{day}".encode()
    hash_val = int(hashlib.md5(seed).hexdigest(), 16)
    percentile = hash_val % 100

    if percentile < 70:
        return 0
    elif percentile < 90:
        return 5
    else:
        return 15


# First entry special bonus
XP_FIRST_ENTRY = 50
XP_ENTRY_BASE = 10

# Task XP
XP_TASK_COMPLETED = 5
XP_FULL_DAY_BONUS = 15  # 3+ tasks completed
XP_GOAL_MET_BONUS = 15  # Full study hours goal met


# Milestone bonuses (one-time per achievement)
MILESTONE_XP = {
    "first_entry": 50,  # Special first-time bump
    "day_3": 50,        # 3-day streak
    "day_7": 100,       # 1-week streak (jackpot)
    "day_14": 150,      # 2-week streak
    "day_30": 250,      # 1-month streak
    "comeback_1d": 50,  # Return after 1-day miss
    "comeback_3d": 75,  # Return after 3+ day miss
    "consistency_21": 150,  # 21 days logged (not necessarily consecutive)
}

# Level thresholds (optimized for D7 habit formation)
LEVEL_THRESHOLDS = {
    1: 0,      # Seed: starts at 0
    2: 50,     # Sprout: hit around day 3-5 with daily logging
    3: 120,    # Young Plant: hit around day 7 with daily + tasks
    4: 220,    # Blooming: week 2
    5: 400,    # Flourishing: week 3+
    6: 650,    # Canopy: deeper consistency
    7: 950,    # Wildwood: sustained habit lock-in
    8: 1350,   # Evergreen: long-term mastery
}

LEVEL_NAMES = {
    1: "Seed",
    2: "Sprout",
    3: "Young Plant",
    4: "Blooming",
    5: "Flourishing",
    6: "Canopy",
    7: "Wildwood",
    8: "Evergreen",
}

# Mood states (thresholds)
MOOD_THRESHOLDS = {
    "thriving": {"min_perf": 70, "max_burnout": 30},
    "healthy": {"min_perf": 50, "max_burnout": 50},
    "tired": {"min_perf": 40, "max_burnout": 50},  # Burnout > 50 OR perf < 40
    "stressed": {"min_perf": 0, "max_burnout": 100},  # Burnout > 70 (checked separately)
}

# Visual progression stages within each level (4 stages per level)
VISUAL_STAGES = {
    1: ["🌰", "🌰✨", "🌱", "🌱✨"],
    2: ["🌿", "🌿✨", "🌿🌿", "🌸"],
    3: ["🪴", "🪴✨", "🪴🌸", "🌸🌸"],
    4: ["🌸🌸✨", "🌻", "🌻✨", "🌺"],
    5: ["🌺✨", "🌺🌺", "🌺🌺✨", "🎄"],
    6: ["🌳", "🌳✨", "🌳🌿", "🌳🌟"],
    7: ["🌲", "🌲✨", "🌲🌿", "🌲🌟"],
    8: ["🌌", "🌟", "✨🌲", "💫🌿"],
}

# Companion mini-mood emojis (based on today's single entry)
INSTANT_MOOD_EMOJI = {
    "great": "💚",      # Good sleep, low stress
    "good": "💙",       # Decent day
    "okay": "🟡",       # Mixed signals
    "tough": "😟",      # High stress or low sleep
    "really_tough": "😢",  # Very bad day
}


# ============================================================
# STREAK COMPUTATION
# ============================================================

def get_current_streak(username: str) -> int:
    """
    Compute entry streak: consecutive days ending today with logged entries.
    Timezone-aware: compares YYYY-MM-DD strings (server-side dates).
    """
    df = get_entries_dataframe(username)
    if df.empty or "date" not in df.columns:
        return 0

    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp.now().normalize()
    streak = 0

    for i in range(60):  # Check last 60 days max
        check_date = (today - pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        has_entry = any(df["date"].dt.strftime("%Y-%m-%d") == check_date)

        if has_entry:
            if i == 0:  # Today
                streak += 1
            else:
                streak += 1
        else:
            if i > 0:
                break

    return streak


def days_since_last_entry(username: str) -> int:
    """How many days since last log? (0 = today, 1 = yesterday, etc.)"""
    df = get_entries_dataframe(username)
    if df.empty or "date" not in df.columns:
        return 999  # Never logged

    last_date = pd.to_datetime(df["date"].iloc[-1])
    today = pd.Timestamp.now().normalize()
    delta = (today - last_date).days
    return delta


# ============================================================
# INSTANT MOOD (TODAY'S ENTRY ONLY)
# ============================================================

def compute_instant_mood(sleep_hours: float, stress: int, productivity: int) -> tuple[str, str]:
    """
    Compute today's mood from a single entry (not rolling average).
    Returns: (mood_state, emoji)
    
    Used to show immediate reaction after entry submission.
    """
    sleep_score = sleep_hours / 8.0  # 8h is baseline
    stress_score = (10 - stress) / 10.0  # Inverse: high stress = low score
    productivity_score = productivity / 10.0

    overall = (sleep_score * 0.4 + stress_score * 0.35 + productivity_score * 0.25)

    if overall >= 0.75:
        return "great", INSTANT_MOOD_EMOJI["great"]
    elif overall >= 0.6:
        return "good", INSTANT_MOOD_EMOJI["good"]
    elif overall >= 0.45:
        return "okay", INSTANT_MOOD_EMOJI["okay"]
    elif overall >= 0.3:
        return "tough", INSTANT_MOOD_EMOJI["tough"]
    else:
        return "really_tough", INSTANT_MOOD_EMOJI["really_tough"]


# ============================================================
# TREND MOOD (7-DAY ROLLING AVERAGE)
# ============================================================

def compute_trend_mood(username: str, performance: float, burnout: float, streak: int) -> str:
    """
    Compute companion mood from performance/burnout trends.
    Also considers streak/dormant state.
    """
    if streak == 0 and days_since_last_entry(username) > 7:
        return "dormant"

    if burnout > 70:
        return "stressed"
    elif burnout > 50 or performance < 40:
        return "tired"
    elif performance > 70 and burnout < 30:
        return "thriving"
    elif performance > 50 and burnout < 50:
        return "healthy"
    else:
        return "healthy"  # Default


# ============================================================
# XP & LEVEL COMPUTATION
# ============================================================

def compute_total_xp_from_history(username: str) -> dict:
    """
    Compute total XP earned from entry history.
    Returns: {"xp_current": int, "events": list}
    
    This is a fresh calculation from entries (for MVP).
    In Phase 2+, we'll persist companion_state in DB for performance.
    """
    df = get_entries_dataframe(username)
    events = []
    total_xp = 0

    if len(df) < 1:
        return {"xp_current": 0, "events": events, "entry_count": 0}

    # Track dates seen for milestone detection
    entry_dates = sorted(set(df["date"].astype(str).str[:10]))
    today_str = date.today().isoformat()

    # First entry bonus (always award on first entry in history)
    if len(entry_dates) > 0:
        total_xp += XP_FIRST_ENTRY
        events.append({
            "event": "first_entry",
            "xp": XP_FIRST_ENTRY,
            "date": entry_dates[0],
        })

    # Daily entry XP (compute for each date, applying streak bonus)
    for idx, entry_date in enumerate(entry_dates):
        # Compute streak at this point in history
        streak_at_date = idx + 1
        entry_xp = get_entry_xp(streak_at_date)

        # Variable bonus for this date
        variable_bonus = get_variable_xp_bonus(username, entry_date)
        entry_xp += variable_bonus

        total_xp += entry_xp
        events.append({
            "event": "daily_entry",
            "xp": entry_xp,
            "date": entry_date,
            "streak_day": streak_at_date,
        })

        # Milestone bonuses (one-time, for this specific date)
        if streak_at_date == 3:
            total_xp += MILESTONE_XP["day_3"]
            events.append({"event": "milestone_day_3", "xp": MILESTONE_XP["day_3"], "date": entry_date})
        elif streak_at_date == 7:
            total_xp += MILESTONE_XP["day_7"]
            events.append({"event": "milestone_day_7", "xp": MILESTONE_XP["day_7"], "date": entry_date})
        elif streak_at_date == 14:
            total_xp += MILESTONE_XP["day_14"]
            events.append({"event": "milestone_day_14", "xp": MILESTONE_XP["day_14"], "date": entry_date})
        elif streak_at_date == 30:
            total_xp += MILESTONE_XP["day_30"]
            events.append({"event": "milestone_day_30", "xp": MILESTONE_XP["day_30"], "date": entry_date})

    # Consistency milestone (21 unique dates logged)
    if len(entry_dates) >= 21:
        total_xp += MILESTONE_XP["consistency_21"]
        events.append({"event": "consistency_21", "xp": MILESTONE_XP["consistency_21"], "date": today_str})

    # TODO: Task XP (integrate with task manager in Phase 2)

    return {"xp_current": total_xp, "events": events, "entry_count": len(entry_dates)}


def get_level_from_xp(xp: int) -> int:
    """Determine level from total XP."""
    for level in sorted(LEVEL_THRESHOLDS.keys(), reverse=True):
        if xp >= LEVEL_THRESHOLDS[level]:
            return level
    return 1


def get_xp_to_next_level(xp: int, current_level: int) -> int:
    """How many XP needed to reach next level?"""
    max_level = max(LEVEL_THRESHOLDS)
    if current_level >= max_level:
        return 0  # Max level

    next_level_threshold = LEVEL_THRESHOLDS[current_level + 1]
    return max(0, next_level_threshold - xp)


def get_level_progress_percent(xp: int, current_level: int) -> float:
    """Progress bar percentage within current level (0-100)."""
    current_threshold = LEVEL_THRESHOLDS[current_level]
    max_level = max(LEVEL_THRESHOLDS)
    if current_level >= max_level:
        return 100.0

    next_threshold = LEVEL_THRESHOLDS[current_level + 1]
    range_size = next_threshold - current_threshold

    if range_size <= 0:
        return 0.0

    progress = (xp - current_threshold) / range_size
    return min(100.0, max(0.0, progress * 100))


def get_visual_stage(xp: int, current_level: int) -> str:
    """Get emoji/visual representation based on XP progress within level."""
    if current_level not in VISUAL_STAGES:
        return "🌰"  # Fallback

    stages = VISUAL_STAGES[current_level]
    progress_pct = get_level_progress_percent(xp, current_level)

    # 4 stages per level based on 25% increments
    stage_idx = min(3, int(progress_pct / 25))
    return stages[stage_idx]


# ============================================================
# COMEBACK LOGIC
# ============================================================

def get_comeback_state(username: str) -> dict | None:
    """
    Detect if user is in comeback scenario (missed 1+ days, now logging again).
    Returns comeback details or None.
    """
    days_absent = days_since_last_entry(username)

    if days_absent == 0:
        return None  # Logged today already
    elif days_absent == 1:
        return {"days_absent": 1, "bonus_xp": MILESTONE_XP["comeback_1d"], "type": "brief"}
    elif days_absent >= 3:
        return {"days_absent": days_absent, "bonus_xp": MILESTONE_XP["comeback_3d"], "type": "revival"}
    else:
        return None  # 2-day absence (not yet comeback bonus)


# ============================================================
# MAIN SUMMARY COMPUTATION
# ============================================================

def compute_companion_summary(username: str, analysis_result: dict | None = None) -> dict:
    """
    Core function: compute full companion state from entries + analysis + tasks.
    Called on dashboard load, entry submission, task completion.
    
    Returns comprehensive companion state for API/frontend.
    """
    df = get_entries_dataframe(username)

    # Insufficient data state
    if df.empty or len(df) < 1:
        return {
            "level": 1,
            "xp_current": 0,
            "xp_threshold": 0,
            "xp_to_level_up": LEVEL_THRESHOLDS[2],
            "level_progress_pct": 0,
            "visual_stage": "🌰",
            "mood_trend": "dormant",
            "mood_emoji": "🌱",
            "streak": 0,
            "last_activity_date": None,
            "performance": 0,
            "burnout": 0,
            "trend": "stable",
            "comeback_available": False,
            "milestones_reached": [],
            "entry_count": 0,
            "events": [],
        }

    # Core metrics
    streak = get_current_streak(username)
    if len(df) > 0:
        raw_last_date = df.iloc[-1].get("date", pd.Timestamp.now())
        last_date = pd.to_datetime(raw_last_date).strftime("%Y-%m-%d")
    else:
        last_date = None
    entry_count = len(df)

    # XP & level
    xp_data = compute_total_xp_from_history(username)
    xp_current = xp_data["xp_current"]
    level = get_level_from_xp(xp_current)
    xp_to_level_up = get_xp_to_next_level(xp_current, level)
    level_progress_pct = get_level_progress_percent(xp_current, level)
    visual_stage = get_visual_stage(xp_current, level)

    # Performance & burnout from analysis
    if analysis_result and "latest" in analysis_result:
        perf = float(analysis_result["latest"].get("performance_score", 50))
        burnout = float(analysis_result["latest"].get("burnout_risk", 50))
        chart = analysis_result.get("chart_data", [])

        # Trend: compare last 7 days vs previous 7
        if len(chart) >= 14:
            last7_perf = [c.get("performance_score", 50) for c in chart[-7:]]
            prev7_perf = [c.get("performance_score", 50) for c in chart[-14:-7]]
            perf_trend = sum(last7_perf) / 7 - sum(prev7_perf) / 7
            if perf_trend > 5:
                trend = "improving"
            elif perf_trend < -5:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
    else:
        perf = 50
        burnout = 50
        trend = "stable"

    # Mood (trend-based)
    mood_trend = compute_trend_mood(username, perf, burnout, streak)

    # Instant mood (today's entry if exists)
    today_str = date.today().isoformat()
    today_entry = get_entry_row(username, today_str)
    if today_entry:
        instant_mood, instant_emoji = compute_instant_mood(
            float(today_entry.get("sleep_hours", 8)),
            int(today_entry.get("stress", 5)),
            int(today_entry.get("productivity", 5)),
        )
        mood_emoji = instant_emoji
    else:
        mood_emoji = "🌿" if mood_trend == "healthy" else "💚" if mood_trend == "thriving" else "😴"

    # Milestones reached
    milestones = []
    if streak >= 30:
        milestones.append("30-day-streak")
    elif streak >= 14:
        milestones.append("14-day-streak")
    elif streak >= 7:
        milestones.append("7-day-streak")

    if entry_count >= 21:
        milestones.append("21-entries")

    if xp_current >= LEVEL_THRESHOLDS[3]:
        milestones.append("level-3")

    # Comeback state
    comeback = get_comeback_state(username)
    comeback_available = comeback is not None

    return {
        "level": level,
        "level_name": LEVEL_NAMES.get(level, "Unknown"),
        "xp_current": xp_current,
        "xp_threshold": LEVEL_THRESHOLDS[level],
        "xp_to_level_up": xp_to_level_up,
        "level_progress_pct": round(level_progress_pct, 1),
        "visual_stage": visual_stage,
        "mood_trend": mood_trend,
        "mood_emoji": mood_emoji,
        "streak": streak,
        "last_activity_date": last_date,
        "days_since_activity": days_since_last_entry(username),
        "performance": round(perf, 1),
        "burnout": round(burnout, 1),
        "trend": trend,
        "comeback_available": comeback_available,
        "comeback_bonus_xp": comeback["bonus_xp"] if comeback else 0,
        "milestones_reached": milestones,
        "entry_count": entry_count,
    }


# ============================================================
# DIALOGUE / COPY GENERATION
# ============================================================

def generate_companion_dialogue(summary: dict) -> str:
    """Generate supportive companion dialogue based on state."""
    level = summary["level"]
    mood = summary["mood_trend"]
    streak = summary["streak"]

    if streak == 0:
        if level == 1:
            return "I'm here when you need me. 🌱"
        else:
            return "Let's start fresh today. 💙"

    if streak == 1:
        return "You brought me to life! Thank you. 💚"
    elif streak == 3:
        return "Three days of care! I'm growing. 🌿"
    elif streak == 7:
        return "A week! You did it. 🌸 I'm blooming."
    elif streak == 14:
        return "Two weeks! Your dedication matters. 🌻"
    elif streak == 30:
        return "A month of care. I'm flourishing. 🌺"

    if mood == "thriving":
        return "Your energy is beautiful. Keep it up! ✨"
    elif mood == "stressed":
        return "Take it easy today. I'm here for you. 💙"
    elif mood == "tired":
        return "Rest is productivity too. Be kind to yourself. 💤"
    elif mood == "dormant":
        return "I'm waiting for you. 🌱 Log when ready."

    return "Your wellbeing matters. 💚"
