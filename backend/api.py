from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import os
import hashlib
import io
import numpy as np

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
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        os.environ.get("FRONTEND_URL", "https://app-project-uk97.vercel.app"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

USERS_DIR = "users"
os.makedirs(USERS_DIR, exist_ok=True)

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