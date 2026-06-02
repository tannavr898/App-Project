from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import os
import io
import json
import time
import threading
import logging
import importlib
import numpy as np
from datetime import datetime
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from time import perf_counter
from pywebpush import webpush, WebPushException

from fastapi import UploadFile, File

try:
    from .auth import register_user, authenticate_user, create_token, decode_token
    from .data_store import (
        ensure_database,
        get_entries_dataframe,
        get_entries_version,
        get_entry_row,
        get_push_subscriptions,
        get_reminder_preferences,
        get_reminder_state,
        get_user,
        has_entries,
        list_users as store_list_users,
        remove_push_subscription,
        set_reminder_state,
        set_reminder_preferences,
        upsert_push_subscription,
        upsert_entry,
        log_companion_event,
    )
    from .student_data import StudentData
    from .performance_model import PerformanceModel
    from .recommendation_engine import RecommendationEngine
    from .task_manager import TaskManager
    from .companion import compute_companion_summary
except ImportError:
    from auth import register_user, authenticate_user, create_token, decode_token
    from data_store import (
        ensure_database,
        get_entries_dataframe,
        get_entries_version,
        get_entry_row,
        get_push_subscriptions,
        get_reminder_preferences,
        get_reminder_state,
        get_user,
        has_entries,
        list_users as store_list_users,
        remove_push_subscription,
        set_reminder_state,
        set_reminder_preferences,
        upsert_push_subscription,
        upsert_entry,
        log_companion_event,
    )
    from student_data import StudentData
    from performance_model import PerformanceModel
    from recommendation_engine import RecommendationEngine
    from task_manager import TaskManager
    from companion import compute_companion_summary

# --------------------------------------------------
# Cache + rate limiting
# --------------------------------------------------
_analysis_cache = {}
_analysis_cache_lock = threading.Lock()
_analysis_executor = ThreadPoolExecutor(max_workers=int(os.environ.get("ANALYSIS_WORKERS", "1")))
_analysis_jobs = {}
_analysis_jobs_lock = threading.Lock()


def _csv_version(username: str) -> str:
    try:
        return int(get_entries_version(username))
    except Exception:
        return 0


def _invalidate_user_cache(username: str):
    with _analysis_cache_lock:
        _analysis_cache.pop(username, None)


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = defaultdict(deque)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._requests[key]
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_requests:
                return False
            q.append(now)
            return True


_entry_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.environ.get("RATE_LIMIT_ENTRIES_MAX", "6")),
    window_seconds=int(os.environ.get("RATE_LIMIT_ENTRIES_WINDOW_SEC", "60")),
)
_analysis_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.environ.get("RATE_LIMIT_ANALYSIS_MAX", "40")),
    window_seconds=int(os.environ.get("RATE_LIMIT_ANALYSIS_WINDOW_SEC", "60")),
)
_auth_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.environ.get("RATE_LIMIT_AUTH_MAX", "15")),
    window_seconds=int(os.environ.get("RATE_LIMIT_AUTH_WINDOW_SEC", "60")),
)
_import_limiter = SlidingWindowRateLimiter(
    max_requests=int(os.environ.get("RATE_LIMIT_IMPORT_MAX", "4")),
    window_seconds=int(os.environ.get("RATE_LIMIT_IMPORT_WINDOW_SEC", "60")),
)


def _rate_limit_key(request: Request, scope: str, user_hint: str = "") -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    ip = forwarded or (request.client.host if request.client else "unknown")
    hint = user_hint.strip().lower()
    return f"{scope}:{ip}:{hint}"


def _build_analysis_result(username: str) -> tuple[str, dict]:
    version = _csv_version(username)

    entries_df = get_entries_dataframe(username)
    if entries_df.empty:
        raise HTTPException(status_code=400, detail="Not enough data yet")

    data = StudentData(dataframe=entries_df)
    df = data.get_dataframe()

    perf_model = PerformanceModel()
    perf_model.train(df)
    df = perf_model.add_performance_score(df)

    baselines = perf_model.get_baselines(df)
    profile = perf_model.get_user_profile() if perf_model.trained else {}

    plans = {}
    optimal_plan = None
    if perf_model.trained:
        engine = RecommendationEngine(perf_model)
        plans = engine.find_all_plans(df)
        recommended_key = plans.get("recommended", "comfortable")
        optimal_plan = plans.get(recommended_key)

    chart_data = df.tail(30)[
        [
            "date", "burnout_risk", "performance_score",
            "avg_sleep_7", "avg_stress_7", "avg_fatigue_7", "avg_productivity_7",
        ]
    ].copy()
    chart_data["date"] = chart_data["date"].astype(str)

    latest = df.iloc[-1]
    result = {
        "latest": {
            "performance_score":  round(float(latest.get("performance_score", 0)), 1),
            "burnout_risk":        round(float(latest.get("burnout_risk", 0)), 1),
            "avg_sleep_7":         round(float(latest["avg_sleep_7"]), 2),
            "avg_stress_7":        round(float(latest["avg_stress_7"]), 1),
            "avg_fatigue_7":       round(float(latest["avg_fatigue_7"]), 1),
            "avg_productivity_7":  round(float(latest["avg_productivity_7"]), 1),
            "avg_load":            round(float(latest["avg_load"]), 2),
        },
        "baselines":        {k: round(float(v), 2) for k, v in baselines.items()},
        "profile":          {k: round(float(v), 4) for k, v in profile.items()},
        "optimal_plan":     optimal_plan,
        "plans":            plans,
        "recommended_mode": plans.get("recommended", "comfortable"),
        "chart_data":       chart_data.to_dict(orient="records"),
        "total_entries":    len(df),
    }
    return version, result


def _store_analysis_result(username: str, version: str, result: dict) -> None:
    current_version = _csv_version(username)
    if current_version != version:
        return
    with _analysis_cache_lock:
        _analysis_cache[username] = {"version": version, "result": result}


def _run_analysis_job(username: str, version: str):
    try:
        built_version, result = _build_analysis_result(username)
        _store_analysis_result(username, built_version, result)
    except Exception as exc:
        logger.exception("analysis_job_failed username=%s version=%s error=%s", username, version, exc)
    finally:
        with _analysis_jobs_lock:
            state = _analysis_jobs.get(username)
            if state and state.get("version") == version:
                state["future"] = None
            desired_version = state.get("desired_version") if state else None

        current_version = _csv_version(username)
        if desired_version is not None and current_version and desired_version > version:
            _schedule_analysis_refresh(username, desired_version)


def _schedule_analysis_refresh(username: str, version: str | None = None) -> None:
    if version is None:
        version = _csv_version(username)
    if not version:
        return

    with _analysis_jobs_lock:
        state = _analysis_jobs.setdefault(username, {"future": None, "version": None, "desired_version": None})
        state["desired_version"] = max(int(state["desired_version"] or 0), int(version))
        active_future = state.get("future")
        active_version = state.get("version")
        if active_future and not active_future.done() and active_version == version:
            return
        state["version"] = version
        state["future"] = _analysis_executor.submit(_run_analysis_job, username, version)


def _cached_analysis(username: str) -> tuple[str | None, dict | None]:
    with _analysis_cache_lock:
        cached = _analysis_cache.get(username)
        if not cached:
            return None, None
        return cached.get("version"), cached.get("result")

# --------------------------------------------------
# App + CORS
# --------------------------------------------------
app = FastAPI(title="Student Wellness API")
ensure_database()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("pulse.api")

sentry_dsn = os.environ.get("SENTRY_DSN", "").strip()
if sentry_dsn:
    try:
        sentry_sdk = importlib.import_module("sentry_sdk")
        fastapi_integration = importlib.import_module("sentry_sdk.integrations.fastapi")
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[fastapi_integration.FastApiIntegration()],
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production"),
        )
        logger.info("Sentry initialized")
    except Exception as exc:
        logger.warning("Sentry disabled: %s", exc)

default_origins = {
    "https://pulsewellness.vercel.app",
    "https://www.pulsewellness.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
}

# Accept Vercel preview deployments (e.g. branch-name-project.vercel.app).
default_origin_regex = os.environ.get(
    "FRONTEND_ORIGIN_REGEX",
    r"https://([a-zA-Z0-9-]+\.)*vercel\.app",
)

frontend_url = os.environ.get("FRONTEND_URL", "").strip()
if frontend_url:
    default_origins.add(frontend_url)

frontend_urls = os.environ.get("FRONTEND_URLS", "").strip()
if frontend_urls:
    for origin in frontend_urls.split(","):
        origin = origin.strip()
        if origin:
            default_origins.add(origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(default_origins),
    allow_origin_regex=default_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed_ms = (perf_counter() - started) * 1000
        logger.exception(
            "request_failed method=%s path=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            elapsed_ms,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    elapsed_ms = (perf_counter() - started) * 1000
    response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"
    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response

USERS_DIR = "users"
os.makedirs(USERS_DIR, exist_ok=True)

PUSH_SUBSCRIPTION_FILE = os.path.join(USERS_DIR, "push_subscriptions.json")
PUSH_REMINDER_STATE_FILE = os.path.join(USERS_DIR, "push_reminder_state.json")
VAPID_PUBLIC_KEY = os.environ.get(
    "VAPID_PUBLIC_KEY",
    "BHyCQIIrX3kTHzOe00Wj0N7mC-BN_oG860R3p62uCCQ8nX8VRJAtzMDo89VN9oXEWC79HpXstivOySqi-hDyDPs"
)
VAPID_PRIVATE_KEY = os.environ.get(
    "VAPID_PRIVATE_KEY",
    "zGGsEQAU4ilGg8vnJUoT9XrTISzNqufqIKRtO2M6E5k"
)
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:hello@pulseapp.local")

# --------------------------------------------------
# Pydantic models
# --------------------------------------------------
class NewEntry(BaseModel):
    username: str
    date: str
    sleep_hours: float
    study_hours: float
    training_hours: float
    stress: int
    fatigue: int
    productivity: int

class NewTask(BaseModel):
    username: str
    name: str
    hours: float
    carry_over: bool = False
    category: str = "other"
    today: Optional[str] = None

class TaskAction(BaseModel):
    username: str
    task_id: str
    today: Optional[str] = None

class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class PushSubscription(BaseModel):
    username: str
    subscription: dict

class PushUnsubscribe(BaseModel):
    username: str
    endpoint: str

class ReminderPreferences(BaseModel):
    username: str
    reminder_time: str = "20:30"
    log_enabled: bool = True
    task_enabled: bool = True
    timezone: str = "local"

# --------------------------------------------------
# Auth dependency
# --------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    username = decode_token(credentials.credentials)
    if username is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return username

# --------------------------------------------------
# Helpers
# --------------------------------------------------
def get_user_file(username: str) -> str:
    return os.path.join(USERS_DIR, f"{username}.csv")

def user_exists(username: str) -> bool:
    if username.strip().lower() == "dev":
        return True
    return get_user(username) is not None or has_entries(username)

# --------------------------------------------------
def _store_subscription(username: str, subscription: dict):
    upsert_push_subscription(username, subscription)


def _remove_subscription(username: str, endpoint: str):
    remove_push_subscription(username, endpoint)


def _send_push(subscription: dict, payload: dict):
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims={"sub": VAPID_SUBJECT},
        )
        return True
    except WebPushException as exc:
        if exc.response and exc.response.status_code in {404, 410}:
            return False
        return True
    except Exception:
        return True


def _notify_user(username: str, title: str, message: str, url: str = "/"):
    subs = get_push_subscriptions(username)
    if not subs or not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return

    remaining = []
    for sub in subs:
        payload = {"title": title, "body": message, "url": url}
        keep = _send_push(sub, payload)
        if keep:
            remaining.append(sub)
    if len(remaining) != len(subs):
        if remaining:
            for sub in remaining:
                upsert_push_subscription(username, sub)
        else:
            for sub in subs:
                endpoint = sub.get("endpoint")
                if endpoint:
                    remove_push_subscription(username, endpoint)


def _today_date() -> str:
    return pd.Timestamp.now().normalize().strftime("%Y-%m-%d")


def _minutes_from_time(value: str) -> int:
    try:
        hour, minute = [int(part) for part in str(value).split(":", 1)]
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour * 60 + minute
    except Exception:
        pass
    return 20 * 60 + 30


def _should_send_reminder_now(preferences: dict, now_dt: datetime, last_sent: int) -> bool:
    target_minutes = _minutes_from_time(preferences.get("reminder_time", "20:30"))
    current_minutes = now_dt.hour * 60 + now_dt.minute
    if current_minutes < target_minutes:
        return False
    if last_sent <= 0:
        return True
    last_dt = datetime.fromtimestamp(last_sent)
    return last_dt.date() < now_dt.date()


def _has_unfinished_tasks(username: str) -> bool:
    try:
        tm = TaskManager(username, USERS_DIR)
        tasks = tm.get_todays_tasks()
        return any(not t.get("completed") for t in tasks)
    except Exception:
        return False


def _needs_log_entry(username: str) -> bool:
    if not user_exists(username):
        return False
    df = get_entries_dataframe(username)
    if df.empty or "date" not in df.columns:
        return True
    today = _today_date()
    return not any(df["date"].astype(str).str[:10] == today)


def _dispatch_push_reminders():
    subscriptions = {username: get_push_subscriptions(username) for username in store_list_users()}
    now = int(time.time())
    now_dt = datetime.now()
    for username, subs in subscriptions.items():
        if not subs:
            continue
        preferences = get_reminder_preferences(username)
        last_sent = int(preferences.get("last_sent") or get_reminder_state(username))
        if not _should_send_reminder_now(preferences, now_dt, last_sent):
            continue
        if preferences.get("log_enabled", True) and _needs_log_entry(username):
            _notify_user(username, "Log your Pulse entry", "You haven't logged today's wellness entry yet.", "/log")
            set_reminder_state(username, now)
        elif preferences.get("task_enabled", True) and _has_unfinished_tasks(username):
            _notify_user(username, "Finish your tasks", "You have unfinished tasks waiting in Pulse.", "/tasks")
            set_reminder_state(username, now)


def _start_push_reminder_thread():
    def worker():
        while True:
            try:
                _dispatch_push_reminders()
            except Exception:
                pass
            time.sleep(15 * 60)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

@app.on_event("startup")
def _startup_event():
    _start_push_reminder_thread()


def build_analysis(username: str) -> dict:
    version = _csv_version(username)
    cached_version, cached_result = _cached_analysis(username)
    if cached_version == version and cached_result is not None:
        return cached_result

    with _analysis_jobs_lock:
        state = _analysis_jobs.get(username)
        active_future = state.get("future") if state else None
        active_version = state.get("version") if state else None

    if active_future and not active_future.done():
        if cached_result is not None:
            return cached_result

        # Wait briefly so callers can receive ready data in a single request cycle.
        wait_seconds = float(os.environ.get("ANALYSIS_WAIT_TIMEOUT_SEC", "8"))
        try:
            active_future.result(timeout=wait_seconds)
        except FutureTimeoutError:
            raise HTTPException(status_code=202, detail="Analysis is being refreshed. Please retry in a moment.")
        except Exception as exc:
            logger.exception("analysis_future_failed username=%s error=%s", username, exc)

        fresh_version, fresh_result = _cached_analysis(username)
        current_version = _csv_version(username)
        if fresh_result is not None and fresh_version == current_version:
            return fresh_result

        # Fallback: compute synchronously if background run finished without a cacheable result.
        built_version, result = _build_analysis_result(username)
        _store_analysis_result(username, built_version, result)
        return result

    started = perf_counter()
    built_version, result = _build_analysis_result(username)
    _store_analysis_result(username, built_version, result)
    logger.info(
        "analysis_built username=%s entries=%s duration_ms=%.2f",
        username,
        result.get("total_entries", 0),
        (perf_counter() - started) * 1000,
    )
    return result

# --------------------------------------------------
# Auth routes
# --------------------------------------------------
@app.post("/auth/register")
def register(req: RegisterRequest, request: Request):
    rl_key = _rate_limit_key(request, "auth", req.username)
    if not _auth_limiter.is_allowed(rl_key):
        raise HTTPException(status_code=429, detail="Too many auth attempts. Please wait and try again.")
    try:
        user  = register_user(req.username, req.password)
        token = create_token(user["username"])
        return {"username": user["username"], "token": token}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login")
def login(req: LoginRequest, request: Request):
    rl_key = _rate_limit_key(request, "auth", req.username)
    if not _auth_limiter.is_allowed(rl_key):
        raise HTTPException(status_code=429, detail="Too many auth attempts. Please wait and try again.")

    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(user["username"])

    # Seed dev account with sample data on first login
    if user.get("is_dev") and not has_entries("dev"):
        _seed_dev_data()

    return {"username": user["username"], "token": token}


@app.get("/auth/me")
def me(current_user: str = Depends(get_current_user)):
    return {"username": current_user}

# --------------------------------------------------
# Dev data seeding
# --------------------------------------------------
def _seed_dev_data():
    """Generate 30 days of realistic sample data for the dev account."""
    np.random.seed(int(pd.Timestamp.now().timestamp()))
    dates      = pd.date_range(end=pd.Timestamp.today(), periods=30, freq="D")
    sleep      = np.clip(np.random.normal(7.5, 0.8, 30), 5.5, 10.0)
    study      = np.clip(np.random.normal(3.5, 1.0, 30), 0.5, 7.0)
    training   = np.clip(np.random.normal(1.0, 0.5, 30), 0.0, 3.0)
    stress     = np.clip(np.random.randint(3, 9, 30) +
                         np.random.choice([-1, 0, 1], 30), 1, 10).astype(int)
    fatigue    = np.clip(10 - (sleep - 5) * 1.5 +
                         np.random.normal(0, 0.8, 30), 1, 10).astype(int)
    productivity = np.clip(
        7 - stress * 0.3 - fatigue * 0.2 +
        sleep * 0.3 + np.random.normal(0, 0.5, 30),
        1, 10
    ).astype(int)

    df = pd.DataFrame({
        "date":           [d.strftime("%Y-%m-%d") for d in dates],
        "sleep_hours":    np.round(sleep, 1),
        "study_hours":    np.round(study, 1),
        "training_hours": np.round(training, 1),
        "stress":         stress,
        "fatigue":        fatigue,
        "productivity":   productivity,
    })
    for _, row in df.iterrows():
        upsert_entry("dev", {
            "date": row["date"],
            "sleep_hours": row["sleep_hours"],
            "study_hours": row["study_hours"],
            "training_hours": row["training_hours"],
            "stress": row["stress"],
            "fatigue": row["fatigue"],
            "productivity": row["productivity"],
        })
    _schedule_analysis_refresh("dev")


@app.post("/dev/reset")
def reset_dev_data(current_user: str = Depends(get_current_user)):
    """Re-seed the dev account with fresh sample data."""
    if current_user != "dev":
        raise HTTPException(status_code=403, detail="Dev only endpoint")
    _invalidate_user_cache("dev")
    _seed_dev_data()
    return {"message": "Dev data reset with 30 fresh sample days"}

# --------------------------------------------------
# User routes
# --------------------------------------------------
@app.get("/users")
def list_users(current_user: str = Depends(get_current_user)):
    users = store_list_users()
    return {"users": users}


@app.get("/push/vapid_public_key")
def get_push_public_key(
    current_user: str = Depends(get_current_user),
):
    return {"publicKey": VAPID_PUBLIC_KEY}


@app.post("/push/subscribe")
def subscribe_push(
    payload: PushSubscription,
    current_user: str = Depends(get_current_user),
):
    if payload.username != current_user:
        raise HTTPException(status_code=403, detail="Username mismatch")
    if not payload.subscription or not payload.subscription.get("endpoint"):
        raise HTTPException(status_code=400, detail="Invalid subscription")
    _store_subscription(payload.username, payload.subscription)
    return {"message": "Subscription saved"}


@app.post("/push/unsubscribe")
def unsubscribe_push(
    payload: PushUnsubscribe,
    current_user: str = Depends(get_current_user),
):
    if payload.username != current_user:
        raise HTTPException(status_code=403, detail="Username mismatch")
    _remove_subscription(payload.username, payload.endpoint)
    return {"message": "Subscription removed"}


@app.get("/reminders/{username}/preferences")
def get_push_reminder_preferences(
    username: str,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(username, current_user)
    return get_reminder_preferences(effective_username)


@app.post("/reminders/preferences")
def save_push_reminder_preferences(
    payload: ReminderPreferences,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(payload.username, current_user)
    try:
        datetime.strptime(payload.reminder_time, "%H:%M")
    except ValueError:
        raise HTTPException(status_code=400, detail="Reminder time must use HH:MM format")
    return set_reminder_preferences(
        effective_username,
        payload.reminder_time,
        payload.log_enabled,
        payload.task_enabled,
        payload.timezone,
    )


@app.post("/push/send-test")
def send_test_push(
    payload: PushSubscription,
    current_user: str = Depends(get_current_user),
):
    if payload.username != current_user:
        raise HTTPException(status_code=403, detail="Username mismatch")
    _store_subscription(payload.username, payload.subscription)
    _notify_user(payload.username, "Pulse reminder test", "This is a test notification from Pulse.", "/")
    return {"message": "Test push sent"}


@app.get("/users/{username}/analysis")
def get_analysis(
    username: str,
    request: Request,
    current_user: str = Depends(get_current_user),
):
    if username != current_user:
        raise HTTPException(status_code=403, detail="Username mismatch")
    rl_key = _rate_limit_key(request, "analysis", username)
    if not _analysis_limiter.is_allowed(rl_key):
        raise HTTPException(status_code=429, detail="Too many analysis requests. Please wait and retry.")
    if not user_exists(username):
        raise HTTPException(status_code=404, detail="User not found")
    if len(get_entries_dataframe(username)) < 3:
        raise HTTPException(status_code=400, detail="Not enough data yet")
    return build_analysis(username)


@app.get("/users/{username}/entries")
def get_entries(
    username: str,
    current_user: str = Depends(get_current_user),
):
    if username != current_user:
        raise HTTPException(status_code=403, detail="Username mismatch")
    if not user_exists(username):
        raise HTTPException(status_code=404, detail="User not found")
    df = get_entries_dataframe(username)
    return {"entries": df.to_dict(orient="records")}


@app.post("/users/{username}/import")
async def import_csv(
    username: str,
    request: Request,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
):
    if username != current_user:
        raise HTTPException(status_code=403, detail="Username mismatch")
    rl_key = _rate_limit_key(request, "import", username)
    if not _import_limiter.is_allowed(rl_key):
        raise HTTPException(status_code=429, detail="Too many import attempts. Please wait and retry.")

    required_cols = {
        "date", "sleep_hours", "study_hours",
        "training_hours", "stress", "fatigue", "productivity",
    }
    try:
        contents    = await file.read()
        imported_df = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read CSV file.")

    if not required_cols.issubset(imported_df.columns):
        missing = required_cols - set(imported_df.columns)
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")

    for _, row in imported_df.iterrows():
        upsert_entry(username, {
            "date": str(row["date"])[:10],
            "sleep_hours": row["sleep_hours"],
            "study_hours": row["study_hours"],
            "training_hours": row["training_hours"],
            "stress": row["stress"],
            "fatigue": row["fatigue"],
            "productivity": row["productivity"],
        })

    _invalidate_user_cache(username)
    _schedule_analysis_refresh(username)
    return {"message": "Imported successfully", "rows": len(imported_df)}

# --------------------------------------------------
# Entry routes
# --------------------------------------------------
@app.post("/entries")
def add_entry(
    entry: NewEntry,
    request: Request,
    current_user: str = Depends(get_current_user),
):
    if entry.username != current_user:
        raise HTTPException(status_code=403, detail="Username mismatch")
    rl_key = _rate_limit_key(request, "entries", entry.username)
    if not _entry_limiter.is_allowed(rl_key):
        raise HTTPException(status_code=429, detail="Too many entry updates. Please wait and retry.")

    existing_row = get_entry_row(entry.username, entry.date)

    new_row = {
        "date":           entry.date,
        "sleep_hours":    entry.sleep_hours,
        "study_hours":    entry.study_hours,
        "training_hours": entry.training_hours,
        "stress":         entry.stress,
        "fatigue":        entry.fatigue,
        "productivity":   entry.productivity,
    }

    if existing_row is not None:
        unchanged = (
            float(existing_row.get("sleep_hours", -1)) == float(entry.sleep_hours)
            and float(existing_row.get("study_hours", -1)) == float(entry.study_hours)
            and float(existing_row.get("training_hours", -1)) == float(entry.training_hours)
            and int(existing_row.get("stress", -1)) == int(entry.stress)
            and int(existing_row.get("fatigue", -1)) == int(entry.fatigue)
            and int(existing_row.get("productivity", -1)) == int(entry.productivity)
        )
        if unchanged:
            logger.info("entry_noop username=%s date=%s", entry.username, entry.date)
            total_entries = len(get_entries_dataframe(entry.username))
            return {"message": "Entry unchanged", "total_entries": total_entries}

    upsert_entry(entry.username, new_row)
    _invalidate_user_cache(entry.username)
    _schedule_analysis_refresh(entry.username)

    # Log companion event
    try:
        log_companion_event(entry.username, "entry_logged", 10)
    except Exception as e:
        logger.warning("Failed to log companion event: %s", e)

    total_entries = len(get_entries_dataframe(entry.username))
    return {"message": "Entry saved", "total_entries": total_entries}

# --------------------------------------------------
# Task routes
# --------------------------------------------------
def _resolve_task_username(requested_username: str, current_user: str) -> str:
    requested = (requested_username or "").strip().lower()
    effective = (current_user or "").strip().lower()
    if requested and requested != effective:
        logger.warning(
            "task_username_mismatch requested=%s token_user=%s; using token user",
            requested,
            effective,
        )
    return effective


@app.get("/tasks/{username}")
def get_tasks(
    username: str,
    recommended_hours: float = 4.0,
    today: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(username, current_user)
    tm = TaskManager(effective_username, USERS_DIR, today_override=today)
    return {
        "tasks":    tm.get_todays_tasks(),
        "progress": tm.get_progress(recommended_hours),
    }


@app.post("/tasks")
def add_task(
    task: NewTask,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(task.username, current_user)
    tm = TaskManager(effective_username, USERS_DIR, today_override=task.today)
    return tm.add_task(task.name, task.hours, task.carry_over, task.category)


@app.post("/tasks/complete")
def complete_task(
    action: TaskAction,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(action.username, current_user)
    tm = TaskManager(effective_username, USERS_DIR, today_override=action.today)
    try:
        result = tm.complete_task(action.task_id)
        # Log companion event
        try:
            log_companion_event(effective_username, "task_completed", 5)
        except Exception as e:
            logger.warning("Failed to log companion event: %s", e)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tasks/uncomplete")
def uncomplete_task(
    action: TaskAction,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(action.username, current_user)
    tm = TaskManager(effective_username, USERS_DIR, today_override=action.today)
    try:
        return tm.uncomplete_task(action.task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/tasks/{username}/{task_id}")
def delete_task(
    username: str,
    task_id: str,
    today: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(username, current_user)
    tm = TaskManager(effective_username, USERS_DIR, today_override=today)
    try:
        tm.delete_task(task_id)
        return {"message": "Task deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tasks/toggle-carry-over")
def toggle_carry_over(
    action: TaskAction,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(action.username, current_user)
    tm = TaskManager(effective_username, USERS_DIR, today_override=action.today)
    try:
        return tm.toggle_carry_over(action.task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/tasks/{username}/history")
def get_task_history(
    username: str,
    today: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(username, current_user)
    tm = TaskManager(effective_username, USERS_DIR, today_override=today)
    return {"history": tm.get_completion_history()}


@app.get("/tasks/{username}/prefill")
def get_prefill(
    username: str,
    today: Optional[str] = None,
    current_user: str = Depends(get_current_user),
):
    effective_username = _resolve_task_username(username, current_user)
    tm         = TaskManager(effective_username, USERS_DIR, today_override=today)
    hours      = tm.get_todays_hours_by_category()
    total_free = None
    if user_exists(effective_username):
        try:
            df   = get_entries_dataframe(effective_username)
            if not df.empty:
                last       = df.iloc[-1]
                logged     = (
                    float(last.get("sleep_hours", 0)) +
                    float(last.get("study_hours", 0)) +
                    float(last.get("training_hours", 0))
                )
                total_free = round(max(0, 24 - logged), 2)
        except Exception:
            pass
    return {"hours_by_category": hours, "free_hours_yesterday": total_free}


# --------------------------------------------------
# Companion routes
# --------------------------------------------------

@app.get("/companion/{username}/summary")
def get_companion_summary(
    username: str,
    current_user: str = Depends(get_current_user),
):
    """
    Fetch live companion state: level, XP, mood, streak, performance influence.
    Computed fresh from analysis + entries + tasks.
    """
    requested_username = username.strip().lower()
    effective_username = current_user.strip().lower()
    if requested_username != effective_username:
        logger.warning(
            "companion_username_mismatch requested=%s token_user=%s; using token user",
            requested_username,
            effective_username,
        )

    if not user_exists(effective_username):
        raise HTTPException(status_code=404, detail="User not found")

    try:
        # Get analysis data if available
        try:
            analysis = build_analysis(effective_username) if len(get_entries_dataframe(effective_username)) >= 3 else None
        except HTTPException:
            analysis = None

        # Compute companion summary
        summary = compute_companion_summary(effective_username, analysis)

        return {
            "username": effective_username,
            "level": summary["level"],
            "level_name": summary.get("level_name", "Seed"),
            "xp_current": summary["xp_current"],
            "xp_to_level_up": summary["xp_to_level_up"],
            "xp_threshold": summary["xp_threshold"],
            "level_progress_pct": summary["level_progress_pct"],
            "visual_stage": summary["visual_stage"],
            "mood_trend": summary["mood_trend"],
            "mood_emoji": summary.get("mood_emoji", "🌿"),
            "streak": summary["streak"],
            "last_activity_date": summary["last_activity_date"],
            "days_since_activity": summary.get("days_since_activity", 0),
            "performance_influence": {
                "current_performance": summary["performance"],
                "current_burnout": summary["burnout"],
                "trend": summary["trend"],
            },
            "milestones_reached": summary["milestones_reached"],
            "comeback_available": summary.get("comeback_available", False),
            "comeback_bonus_xp": summary.get("comeback_bonus_xp", 0),
            "entry_count": summary["entry_count"],
            "updated_at": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.exception("companion_summary_failed username=%s error=%s", effective_username, exc)
        # Keep dashboard usable even if companion computation fails.
        return {
            "username": effective_username,
            "level": 1,
            "level_name": "Seed",
            "xp_current": 0,
            "xp_to_level_up": 50,
            "xp_threshold": 0,
            "level_progress_pct": 0,
            "visual_stage": "🌰",
            "mood_trend": "dormant",
            "mood_emoji": "🌱",
            "streak": 0,
            "last_activity_date": None,
            "days_since_activity": 0,
            "performance_influence": {
                "current_performance": 0,
                "current_burnout": 0,
                "trend": "stable",
            },
            "milestones_reached": [],
            "comeback_available": False,
            "comeback_bonus_xp": 0,
            "entry_count": 0,
            "updated_at": datetime.utcnow().isoformat(),
            "degraded": True,
        }
