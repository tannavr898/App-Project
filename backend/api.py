from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import os
import hashlib
import io
import json
import time
import threading
import numpy as np
from pywebpush import webpush, WebPushException

from fastapi import UploadFile, File

from auth import register_user, authenticate_user, create_token, decode_token
from student_data import StudentData
from performance_model import PerformanceModel
from recommendation_engine import RecommendationEngine
from task_manager import TaskManager

# --------------------------------------------------
# Cache
# --------------------------------------------------
_analysis_cache = {}

def _csv_hash(username: str) -> str:
    path = get_user_file(username)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

# --------------------------------------------------
# App + CORS
# --------------------------------------------------
app = FastAPI(title="Student Wellness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

class TaskAction(BaseModel):
    username: str
    task_id: str

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
    return os.path.exists(get_user_file(username))

# --------------------------------------------------
# Push helpers
# --------------------------------------------------

def _load_push_subscriptions() -> dict:
    if not os.path.exists(PUSH_SUBSCRIPTION_FILE):
        return {}
    with open(PUSH_SUBSCRIPTION_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_push_subscriptions(data: dict):
    with open(PUSH_SUBSCRIPTION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _load_reminder_state() -> dict:
    if not os.path.exists(PUSH_REMINDER_STATE_FILE):
        return {}
    with open(PUSH_REMINDER_STATE_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_reminder_state(state: dict):
    with open(PUSH_REMINDER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _store_subscription(username: str, subscription: dict):
    subs = _load_push_subscriptions()
    user_subs = subs.get(username, [])
    if not any(s.get("endpoint") == subscription.get("endpoint") for s in user_subs):
        user_subs.append(subscription)
        subs[username] = user_subs
        _save_push_subscriptions(subs)


def _remove_subscription(username: str, endpoint: str):
    subs = _load_push_subscriptions()
    user_subs = subs.get(username, [])
    user_subs = [s for s in user_subs if s.get("endpoint") != endpoint]
    if user_subs or username in subs:
        subs[username] = user_subs
        if not user_subs:
            subs.pop(username, None)
        _save_push_subscriptions(subs)


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
    subs = _load_push_subscriptions().get(username, [])
    if not subs or not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return

    remaining = []
    for sub in subs:
        payload = {"title": title, "body": message, "url": url}
        keep = _send_push(sub, payload)
        if keep:
            remaining.append(sub)
    if len(remaining) != len(subs):
        all_subs = _load_push_subscriptions()
        if remaining:
            all_subs[username] = remaining
        else:
            all_subs.pop(username, None)
        _save_push_subscriptions(all_subs)


def _today_date() -> str:
    return pd.Timestamp.now().normalize().strftime("%Y-%m-%d")


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
    df = pd.read_csv(get_user_file(username))
    if df.empty or "date" not in df.columns:
        return True
    today = _today_date()
    return not any(df["date"].astype(str).str[:10] == today)


def _dispatch_push_reminders():
    state = _load_reminder_state()
    subscriptions = _load_push_subscriptions()
    now = int(time.time())
    for username, subs in subscriptions.items():
        last_sent = state.get(username, 0)
        if now - last_sent < 60 * 60:
            continue
        if _needs_log_entry(username):
            _notify_user(username, "Log your Pulse entry", "You haven't logged today's wellness entry yet.", "/log")
            state[username] = now
        elif _has_unfinished_tasks(username):
            _notify_user(username, "Finish your tasks", "You have unfinished tasks waiting in Pulse.", "/tasks")
            state[username] = now
    _save_reminder_state(state)


def _start_push_reminder_thread():
    def worker():
        while True:
            try:
                _dispatch_push_reminders()
            except Exception:
                pass
            time.sleep(60 * 60)
    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

@app.on_event("startup")
def _startup_event():
    _start_push_reminder_thread()


def build_analysis(username: str) -> dict:
    cache_key = (username, _csv_hash(username))
    if cache_key in _analysis_cache:
        return _analysis_cache[cache_key]

    data = StudentData(get_user_file(username))
    df   = data.get_dataframe()

    perf_model = PerformanceModel()
    perf_model.train(df)
    df = perf_model.add_performance_score(df)

    baselines = perf_model.get_baselines(df)
    profile   = perf_model.get_user_profile() if perf_model.trained else {}

    plans        = {}
    optimal_plan = None
    if perf_model.trained:
        engine       = RecommendationEngine(perf_model)
        plans        = engine.find_all_plans(df)
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

    _analysis_cache[cache_key] = result
    return result

# --------------------------------------------------
# Auth routes
# --------------------------------------------------
@app.post("/auth/register")
def register(req: RegisterRequest):
    try:
        user  = register_user(req.username, req.password)
        token = create_token(user["username"])
        return {"username": user["username"], "token": token}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login")
def login(req: LoginRequest):
    user = authenticate_user(req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_token(user["username"])

    # Seed dev account with sample data on first login
    if user.get("is_dev") and not user_exists("dev"):
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
    df.to_csv(get_user_file("dev"), index=False)


@app.post("/dev/reset")
def reset_dev_data(current_user: str = Depends(get_current_user)):
    """Re-seed the dev account with fresh sample data."""
    if current_user != "dev":
        raise HTTPException(status_code=403, detail="Dev only endpoint")
    _analysis_cache.clear()
    _seed_dev_data()
    return {"message": "Dev data reset with 30 fresh sample days"}

# --------------------------------------------------
# User routes
# --------------------------------------------------
@app.get("/users")
def list_users(current_user: str = Depends(get_current_user)):
    users = [
        f.replace(".csv", "")
        for f in os.listdir(USERS_DIR)
        if f.endswith(".csv")
    ]
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
    current_user: str = Depends(get_current_user),
):
    if not user_exists(username):
        raise HTTPException(status_code=404, detail="User not found")
    if sum(1 for _ in open(get_user_file(username))) < 3:
        raise HTTPException(status_code=400, detail="Not enough data yet")
    return build_analysis(username)


@app.get("/users/{username}/entries")
def get_entries(
    username: str,
    current_user: str = Depends(get_current_user),
):
    if not user_exists(username):
        raise HTTPException(status_code=404, detail="User not found")
    df = pd.read_csv(get_user_file(username))
    df["date"] = df["date"].astype(str)
    return {"entries": df.to_dict(orient="records")}


@app.post("/users/{username}/import")
async def import_csv(
    username: str,
    file: UploadFile = File(...),
    current_user: str = Depends(get_current_user),
):
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

    user_file = get_user_file(username)
    if os.path.exists(user_file):
        existing_df = pd.read_csv(user_file)
        combined    = pd.concat([existing_df, imported_df], ignore_index=True)
        combined    = combined.drop_duplicates(subset="date", keep="last")
        combined.to_csv(user_file, index=False)
    else:
        imported_df.to_csv(user_file, index=False)

    _analysis_cache.clear()
    return {"message": "Imported successfully", "rows": len(imported_df)}

# --------------------------------------------------
# Entry routes
# --------------------------------------------------
@app.post("/entries")
def add_entry(
    entry: NewEntry,
    current_user: str = Depends(get_current_user),
):
    user_file = get_user_file(entry.username)

    if os.path.exists(user_file):
        df = pd.read_csv(user_file)
    else:
        df = pd.DataFrame()

    new_row = {
        "date":           entry.date,
        "sleep_hours":    entry.sleep_hours,
        "study_hours":    entry.study_hours,
        "training_hours": entry.training_hours,
        "stress":         entry.stress,
        "fatigue":        entry.fatigue,
        "productivity":   entry.productivity,
    }

    # Remove any existing entry for the same date
    if not df.empty and "date" in df.columns:
        df = df[df["date"].astype(str).str[:10] != str(entry.date)[:10]]

    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df = df.sort_values("date").reset_index(drop=True)
    df.to_csv(user_file, index=False)
    _analysis_cache.clear()

    return {"message": "Entry saved", "total_entries": len(df)}

# --------------------------------------------------
# Task routes
# --------------------------------------------------
@app.get("/tasks/{username}")
def get_tasks(
    username: str,
    recommended_hours: float = 4.0,
    current_user: str = Depends(get_current_user),
):
    tm = TaskManager(username, USERS_DIR)
    return {
        "tasks":    tm.get_todays_tasks(),
        "progress": tm.get_progress(recommended_hours),
    }


@app.post("/tasks")
def add_task(
    task: NewTask,
    current_user: str = Depends(get_current_user),
):
    tm = TaskManager(task.username, USERS_DIR)
    return tm.add_task(task.name, task.hours, task.carry_over, task.category)


@app.post("/tasks/complete")
def complete_task(
    action: TaskAction,
    current_user: str = Depends(get_current_user),
):
    tm = TaskManager(action.username, USERS_DIR)
    try:
        return tm.complete_task(action.task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tasks/uncomplete")
def uncomplete_task(
    action: TaskAction,
    current_user: str = Depends(get_current_user),
):
    tm = TaskManager(action.username, USERS_DIR)
    try:
        return tm.uncomplete_task(action.task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/tasks/{username}/{task_id}")
def delete_task(
    username: str,
    task_id: str,
    current_user: str = Depends(get_current_user),
):
    tm = TaskManager(username, USERS_DIR)
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
    tm = TaskManager(action.username, USERS_DIR)
    try:
        return tm.toggle_carry_over(action.task_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/tasks/{username}/history")
def get_task_history(
    username: str,
    current_user: str = Depends(get_current_user),
):
    tm = TaskManager(username, USERS_DIR)
    return {"history": tm.get_completion_history()}


@app.get("/tasks/{username}/prefill")
def get_prefill(
    username: str,
    current_user: str = Depends(get_current_user),
):
    tm         = TaskManager(username, USERS_DIR)
    hours      = tm.get_todays_hours_by_category()
    total_free = None
    if user_exists(username):
        try:
            df   = pd.read_csv(get_user_file(username))
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