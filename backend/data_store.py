import json
import os
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

import pandas as pd


USERS_DIR = "users"
LEGACY_DB_PATH = os.path.join(USERS_DIR, "pulse.db")
DEFAULT_DATA_DIR = os.environ.get("PULSE_DATA_DIR", os.path.join(os.path.expanduser("~"), ".pulse"))


def _resolve_db_path() -> str:
    configured = os.environ.get("PULSE_DB_PATH")
    if not configured:
        return os.path.join(DEFAULT_DATA_DIR, "pulse.db")

    configured_abs = os.path.abspath(configured)
    legacy_abs = os.path.abspath(LEGACY_DB_PATH)
    users_dir_abs = os.path.abspath(USERS_DIR)

    if configured_abs == legacy_abs:
        return os.path.join(DEFAULT_DATA_DIR, "pulse.db")
    if os.path.commonpath([configured_abs, users_dir_abs]) == users_dir_abs:
        return os.path.join(DEFAULT_DATA_DIR, "pulse.db")

    return configured


DB_PATH = _resolve_db_path()
DEV_USERNAME = "dev"
DEV_PASSWORD_PLACEHOLDER_HASH = "dev_account_local_only"

_db_lock = threading.Lock()
_db_ready = False


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _ensure_parent_dir() -> None:
    os.makedirs(USERS_DIR, exist_ok=True)
    db_parent = os.path.dirname(os.path.abspath(DB_PATH))
    os.makedirs(db_parent, exist_ok=True)


def _migrate_legacy_database() -> None:
    if os.path.abspath(DB_PATH) == os.path.abspath(LEGACY_DB_PATH):
        return
    if os.path.exists(DB_PATH):
        return
    if not os.path.exists(LEGACY_DB_PATH):
        return

    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    shutil.copy2(LEGACY_DB_PATH, DB_PATH)


@contextmanager
def get_connection():
    _ensure_parent_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=3000")
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_database() -> None:
    global _db_ready
    if _db_ready:
        return
    with _db_lock:
        if _db_ready:
            return
        _ensure_parent_dir()
        _migrate_legacy_database()
        with get_connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_dev INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS entries (
                    username TEXT NOT NULL,
                    entry_date TEXT NOT NULL,
                    sleep_hours REAL NOT NULL,
                    study_hours REAL NOT NULL,
                    training_hours REAL NOT NULL,
                    stress INTEGER NOT NULL,
                    fatigue INTEGER NOT NULL,
                    productivity INTEGER NOT NULL,
                    updated_at_ns INTEGER NOT NULL,
                    PRIMARY KEY (username, entry_date),
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS tasks (
                    username TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    hours REAL NOT NULL,
                    category TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    carry_over INTEGER NOT NULL DEFAULT 0,
                    date_created TEXT NOT NULL,
                    date_completed TEXT,
                    PRIMARY KEY (username, task_id),
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    username TEXT NOT NULL,
                    endpoint TEXT NOT NULL,
                    subscription_json TEXT NOT NULL,
                    PRIMARY KEY (username, endpoint)
                );

                CREATE TABLE IF NOT EXISTS push_reminder_state (
                    username TEXT PRIMARY KEY,
                    last_sent INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS companion_state (
                    username TEXT PRIMARY KEY,
                    level INTEGER NOT NULL DEFAULT 1,
                    xp_current INTEGER NOT NULL DEFAULT 0,
                    xp_threshold INTEGER NOT NULL DEFAULT 0,
                    mood TEXT NOT NULL DEFAULT "healthy",
                    evolved_at TEXT,
                    last_updated_at TEXT NOT NULL,
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS companion_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    xp_gained INTEGER,
                    triggered_at TEXT NOT NULL,
                    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE
                );
                """
            )
            conn.execute(
                """
                INSERT INTO users (username, password_hash, created_at, is_dev)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(username) DO UPDATE SET is_dev = 1
                """,
                (DEV_USERNAME, DEV_PASSWORD_PLACEHOLDER_HASH, _now_iso()),
            )
        _migrate_legacy_data()
        _initialize_companion_states()
        _db_ready = True


def _migrate_legacy_data() -> None:
    auth_path = os.path.join(USERS_DIR, "auth.json")
    if os.path.exists(auth_path):
        try:
            with open(auth_path, "r", encoding="utf-8") as f:
                auth_data = json.load(f)
        except json.JSONDecodeError:
            auth_data = {}
        with get_connection() as conn:
            for username, user in auth_data.items():
                conn.execute(
                    """
                    INSERT INTO users (username, password_hash, created_at, is_dev)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(username) DO UPDATE SET
                        password_hash = excluded.password_hash,
                        created_at = excluded.created_at,
                        is_dev = excluded.is_dev
                    """,
                    (
                        username,
                        user.get("password_hash", ""),
                        user.get("created_at", _now_iso()),
                        1 if user.get("is_dev") else 0,
                    ),
                )

    for filename in os.listdir(USERS_DIR):
        if not filename.endswith(".csv"):
            continue
        username = filename[:-4]
        csv_path = os.path.join(USERS_DIR, filename)
        try:
            df = pd.read_csv(csv_path)
        except Exception:
            continue
        if df.empty or "date" not in df.columns:
            continue
        with get_connection() as conn:
            for _, row in df.iterrows():
                conn.execute(
                    """
                    INSERT INTO entries (
                        username, entry_date, sleep_hours, study_hours,
                        training_hours, stress, fatigue, productivity, updated_at_ns
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(username, entry_date) DO UPDATE SET
                        sleep_hours = excluded.sleep_hours,
                        study_hours = excluded.study_hours,
                        training_hours = excluded.training_hours,
                        stress = excluded.stress,
                        fatigue = excluded.fatigue,
                        productivity = excluded.productivity,
                        updated_at_ns = excluded.updated_at_ns
                    """,
                    (
                        username,
                        str(row.get("date", ""))[:10],
                        float(row.get("sleep_hours", 0) or 0),
                        float(row.get("study_hours", 0) or 0),
                        float(row.get("training_hours", 0) or 0),
                        int(row.get("stress", 0) or 0),
                        int(row.get("fatigue", 0) or 0),
                        int(row.get("productivity", 0) or 0),
                        int(datetime.utcnow().timestamp() * 1_000_000_000),
                    ),
                )

    for filename in os.listdir(USERS_DIR):
        if not filename.endswith("_tasks.json"):
            continue
        username = filename[:-11]
        path = os.path.join(USERS_DIR, filename)
        try:
            with open(path, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        except Exception:
            continue
        if not isinstance(tasks, list):
            continue
        with get_connection() as conn:
            for task in tasks:
                conn.execute(
                    """
                    INSERT INTO tasks (
                        username, task_id, name, hours, category,
                        completed, carry_over, date_created, date_completed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(username, task_id) DO UPDATE SET
                        name = excluded.name,
                        hours = excluded.hours,
                        category = excluded.category,
                        completed = excluded.completed,
                        carry_over = excluded.carry_over,
                        date_created = excluded.date_created,
                        date_completed = excluded.date_completed
                    """,
                    (
                        username,
                        str(task.get("id", "")),
                        str(task.get("name", "")),
                        float(task.get("hours", 0) or 0),
                        str(task.get("category", "other")),
                        1 if task.get("completed") else 0,
                        1 if task.get("carry_over") else 0,
                        str(task.get("date_created", _now_iso()))[:10],
                        task.get("date_completed"),
                    ),
                )


def list_users() -> list[str]:
    ensure_database()
    with get_connection() as conn:
        rows = conn.execute("SELECT username FROM users ORDER BY username").fetchall()
    users = [row[0] for row in rows]
    if "dev" not in users:
        users.append("dev")
    return sorted(set(users))


def get_user(username: str) -> dict | None:
    ensure_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT username, password_hash, created_at, is_dev FROM users WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def upsert_user(username: str, password_hash: str, created_at: str | None = None, is_dev: bool = False) -> None:
    ensure_database()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO users (username, password_hash, created_at, is_dev)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                password_hash = excluded.password_hash,
                created_at = excluded.created_at,
                is_dev = excluded.is_dev
            """,
            (username.strip().lower(), password_hash, created_at or _now_iso(), 1 if is_dev else 0),
        )


def delete_user(username: str) -> None:
    ensure_database()
    with get_connection() as conn:
        conn.execute("DELETE FROM users WHERE username = ?", (username.strip().lower(),))


def has_entries(username: str) -> bool:
    ensure_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM entries WHERE username = ? LIMIT 1",
            (username.strip().lower(),),
        ).fetchone()
    return row is not None


def get_entries_dataframe(username: str) -> pd.DataFrame:
    ensure_database()
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                entry_date AS date,
                sleep_hours,
                study_hours,
                training_hours,
                stress,
                fatigue,
                productivity
            FROM entries
            WHERE username = ?
            ORDER BY entry_date ASC
            """,
            conn,
            params=(username.strip().lower(),),
        )
    return df


def get_entries_version(username: str) -> str:
    ensure_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(updated_at_ns), 0) AS version FROM entries WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    return str(row[0] if row else 0)


def upsert_entry(username: str, entry: dict) -> None:
    ensure_database()
    now_ns = int(datetime.utcnow().timestamp() * 1_000_000_000)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO entries (
                username, entry_date, sleep_hours, study_hours,
                training_hours, stress, fatigue, productivity, updated_at_ns
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username, entry_date) DO UPDATE SET
                sleep_hours = excluded.sleep_hours,
                study_hours = excluded.study_hours,
                training_hours = excluded.training_hours,
                stress = excluded.stress,
                fatigue = excluded.fatigue,
                productivity = excluded.productivity,
                updated_at_ns = excluded.updated_at_ns
            """,
            (
                username.strip().lower(),
                str(entry["date"])[:10],
                float(entry["sleep_hours"]),
                float(entry["study_hours"]),
                float(entry["training_hours"]),
                int(entry["stress"]),
                int(entry["fatigue"]),
                int(entry["productivity"]),
                now_ns,
            ),
        )


def get_entry_row(username: str, entry_date: str) -> dict | None:
    ensure_database()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT entry_date AS date, sleep_hours, study_hours, training_hours, stress, fatigue, productivity
            FROM entries
            WHERE username = ? AND entry_date = ?
            """,
            (username.strip().lower(), str(entry_date)[:10]),
        ).fetchone()
    return dict(row) if row else None


def get_tasks_dataframe(username: str) -> pd.DataFrame:
    ensure_database()
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT
                task_id AS id,
                name,
                hours,
                category,
                completed,
                carry_over,
                date_created,
                date_completed
            FROM tasks
            WHERE username = ?
            ORDER BY date_created ASC, task_id ASC
            """,
            conn,
            params=(username.strip().lower(),),
        )
    if not df.empty:
        df["completed"] = df["completed"].astype(bool)
        df["carry_over"] = df["carry_over"].astype(bool)
    return df


def get_task(username: str, task_id: str) -> dict | None:
    ensure_database()
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT task_id AS id, name, hours, category, completed, carry_over, date_created, date_completed
            FROM tasks
            WHERE username = ? AND task_id = ?
            """,
            (username.strip().lower(), task_id),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["completed"] = bool(result["completed"])
    result["carry_over"] = bool(result["carry_over"])
    return result


def upsert_task(username: str, task: dict) -> None:
    ensure_database()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO tasks (
                username, task_id, name, hours, category,
                completed, carry_over, date_created, date_completed
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(username, task_id) DO UPDATE SET
                name = excluded.name,
                hours = excluded.hours,
                category = excluded.category,
                completed = excluded.completed,
                carry_over = excluded.carry_over,
                date_created = excluded.date_created,
                date_completed = excluded.date_completed
            """,
            (
                username.strip().lower(),
                task["id"],
                task["name"],
                float(task["hours"]),
                task.get("category", "other"),
                1 if task.get("completed") else 0,
                1 if task.get("carry_over") else 0,
                str(task.get("date_created", _now_iso()))[:10],
                task.get("date_completed"),
            ),
        )


def delete_task(username: str, task_id: str) -> None:
    ensure_database()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM tasks WHERE username = ? AND task_id = ?",
            (username.strip().lower(), task_id),
        )


def set_task_completed(username: str, task_id: str, completed: bool) -> dict | None:
    ensure_database()
    now = _now_iso() if completed else None
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET completed = ?, date_completed = ?
            WHERE username = ? AND task_id = ?
            """,
            (1 if completed else 0, now, username.strip().lower(), task_id),
        )
    return get_task(username, task_id)


def toggle_task_carry_over(username: str, task_id: str) -> dict | None:
    ensure_database()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET carry_over = CASE carry_over WHEN 1 THEN 0 ELSE 1 END
            WHERE username = ? AND task_id = ?
            """,
            (username.strip().lower(), task_id),
        )
    return get_task(username, task_id)


def apply_task_carry_over(username: str, today: str | None = None) -> None:
    ensure_database()
    day = (today or datetime.utcnow().date().isoformat())[:10]
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE tasks
            SET date_created = ?
            WHERE username = ?
              AND completed = 0
              AND carry_over = 1
              AND date_created < ?
            """,
            (day, username.strip().lower(), day),
        )


def get_todays_tasks(username: str, today: str | None = None) -> list[dict]:
    ensure_database()
    day = (today or datetime.utcnow().date().isoformat())[:10]
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT task_id AS id, name, hours, category, completed, carry_over, date_created, date_completed
            FROM tasks
            WHERE username = ? AND date_created = ?
            ORDER BY task_id ASC
            """,
            (username.strip().lower(), day),
        ).fetchall()
    tasks = [dict(row) for row in rows]
    for task in tasks:
        task["completed"] = bool(task["completed"])
        task["carry_over"] = bool(task["carry_over"])
    return tasks


def get_completion_history(username: str) -> dict:
    ensure_database()
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT date_created, completed
            FROM tasks
            WHERE username = ?
            ORDER BY date_created ASC, task_id ASC
            """,
            (username.strip().lower(),),
        ).fetchall()
    history = {}
    for row in rows:
        d = row[0]
        if d not in history:
            history[d] = {"completed": 0, "total": 0}
        history[d]["total"] += 1
        if row[1]:
            history[d]["completed"] += 1
    return {
        d: round(v["completed"] / v["total"], 2)
        for d, v in history.items()
        if v["total"] > 0
    }


def get_today_category_hours(username: str, today: str | None = None) -> dict:
    ensure_database()
    day = (today or datetime.utcnow().date().isoformat())[:10]
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT category, hours
            FROM tasks
            WHERE username = ? AND date_created = ? AND completed = 1
            """,
            (username.strip().lower(), day),
        ).fetchall()
    result = {"study": 0.0, "training": 0.0, "personal": 0.0, "other": 0.0}
    for category, hours in rows:
        if category in result:
            result[category] += float(hours or 0)
    return {k: round(v, 2) for k, v in result.items()}


def get_push_subscriptions(username: str) -> list[dict]:
    ensure_database()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT subscription_json FROM push_subscriptions WHERE username = ? ORDER BY endpoint ASC",
            (username.strip().lower(),),
        ).fetchall()
    subscriptions = []
    for row in rows:
        try:
            subscriptions.append(json.loads(row[0]))
        except Exception:
            continue
    return subscriptions


def upsert_push_subscription(username: str, subscription: dict) -> None:
    ensure_database()
    endpoint = subscription.get("endpoint")
    if not endpoint:
        return
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO push_subscriptions (username, endpoint, subscription_json)
            VALUES (?, ?, ?)
            ON CONFLICT(username, endpoint) DO UPDATE SET
                subscription_json = excluded.subscription_json
            """,
            (username.strip().lower(), endpoint, json.dumps(subscription)),
        )


def remove_push_subscription(username: str, endpoint: str) -> None:
    ensure_database()
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM push_subscriptions WHERE username = ? AND endpoint = ?",
            (username.strip().lower(), endpoint),
        )


def get_reminder_state(username: str) -> int:
    ensure_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT last_sent FROM push_reminder_state WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    return int(row[0]) if row else 0


def set_reminder_state(username: str, last_sent: int) -> None:
    ensure_database()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO push_reminder_state (username, last_sent)
            VALUES (?, ?)
            ON CONFLICT(username) DO UPDATE SET
                last_sent = excluded.last_sent
            """,
            (username.strip().lower(), int(last_sent)),
        )


def _initialize_companion_states() -> None:
    """Initialize companion_state for all users on startup."""
    with get_connection() as conn:
        users = conn.execute("SELECT username FROM users").fetchall()
        for (username,) in users:
            conn.execute(
                """
                INSERT OR IGNORE INTO companion_state (username, level, xp_current, mood, last_updated_at)
                VALUES (?, 1, 0, ?, ?)
                """,
                (username, "healthy", _now_iso()),
            )


def get_companion_state(username: str) -> dict | None:
    """Fetch companion state from database."""
    ensure_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT level, xp_current, mood, evolved_at, last_updated_at FROM companion_state WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def upsert_companion_state(username: str, level: int, xp_current: int, mood: str, evolved_at: str | None = None) -> None:
    """Update or insert companion state."""
    ensure_database()
    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO companion_state (username, level, xp_current, mood, evolved_at, last_updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                level = excluded.level,
                xp_current = excluded.xp_current,
                mood = excluded.mood,
                evolved_at = excluded.evolved_at,
                last_updated_at = excluded.last_updated_at
            """,
            (username.strip().lower(), level, xp_current, mood, evolved_at, now),
        )


def log_companion_event(username: str, event_type: str, xp_gained: int) -> None:
    """Log a companion event (entry logged, task completed, milestone, etc.)."""
    ensure_database()
    triggered_at = _now_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO companion_events (username, event_type, xp_gained, triggered_at) VALUES (?, ?, ?, ?)",
            (username.strip().lower(), event_type, xp_gained, triggered_at),
        )


def _initialize_companion_states() -> None:
    """Initialize companion_state for all users on startup."""
    with get_connection() as conn:
        users = conn.execute("SELECT username FROM users").fetchall()
        for (username,) in users:
            conn.execute(
                """
                INSERT OR IGNORE INTO companion_state (username, level, xp_current, mood, last_updated_at)
                VALUES (?, 1, 0, ?, ?)
                """,
                (username, "healthy", _now_iso()),
            )


def get_companion_state(username: str) -> dict | None:
    """Fetch companion state from database."""
    ensure_database()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT level, xp_current, mood, evolved_at, last_updated_at FROM companion_state WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def upsert_companion_state(username: str, level: int, xp_current: int, mood: str, evolved_at: str | None = None) -> None:
    """Update or insert companion state."""
    ensure_database()
    now = _now_iso()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO companion_state (username, level, xp_current, mood, evolved_at, last_updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                level = excluded.level,
                xp_current = excluded.xp_current,
                mood = excluded.mood,
                evolved_at = excluded.evolved_at,
                last_updated_at = excluded.last_updated_at
            """,
            (username.strip().lower(), level, xp_current, mood, evolved_at, now),
        )


def log_companion_event(username: str, event_type: str, xp_gained: int) -> None:
    """Log a companion event (entry logged, task completed, milestone, etc.)."""
    ensure_database()
    triggered_at = _now_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO companion_events (username, event_type, xp_gained, triggered_at) VALUES (?, ?, ?, ?)",
            (username.strip().lower(), event_type, xp_gained, triggered_at),
        )
