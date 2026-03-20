from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import pandas as pd
import os

from student_data import StudentData
from performance_model import PerformanceModel
from recommendation_engine import RecommendationEngine
from task_manager import TaskManager

import hashlib

_analysis_cache = {}

def _csv_hash(username: str) -> str:
    path = get_user_file(username)
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

app = FastAPI(title="Student Wellness API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def get_user_file(username: str) -> str:
    return os.path.join(USERS_DIR, f"{username}.csv")

def user_exists(username: str) -> bool:
    return os.path.exists(get_user_file(username))

def build_analysis(username: str) -> dict:
    """
    Load data, train model, get recommendations.
    Returns a dict ready to send as JSON.
    """
    cache_key = (username, _csv_hash(username))
    if cache_key in _analysis_cache:
        return _analysis_cache[cache_key]
    data = StudentData(get_user_file(username))
    df = data.get_dataframe()

    perf_model = PerformanceModel()
    perf_model.train(df)
    df = perf_model.add_performance_score(df)

    baselines = perf_model.get_baselines(df)
    profile = perf_model.get_user_profile() if perf_model.trained else {}

    optimal_plan = None
    if perf_model.trained:
        engine = RecommendationEngine(perf_model)
        optimal_plan = engine.find_optimal_schedule(df)

    # Build time series for charts (last 30 days)
    chart_data = df.tail(30)[
        ["date", "burnout_risk", "performance_score",
         "avg_sleep_7", "avg_stress_7", "avg_fatigue_7", "avg_productivity_7"]
    ].copy()
    chart_data["date"] = chart_data["date"].astype(str)

    latest = df.iloc[-1]

    result = {
        "latest": {
            "performance_score": round(float(latest.get("performance_score", 0)), 1),
            "burnout_risk": round(float(latest.get("burnout_risk", 0)), 1),
            "avg_sleep_7": round(float(latest["avg_sleep_7"]), 2),
            "avg_stress_7": round(float(latest["avg_stress_7"]), 1),
            "avg_fatigue_7": round(float(latest["avg_fatigue_7"]), 1),
            "avg_productivity_7": round(float(latest["avg_productivity_7"]), 1),
            "avg_load": round(float(latest["avg_load"]), 2),
        },
        "baselines": {k: round(float(v), 2) for k, v in baselines.items()},
        "profile": {k: round(float(v), 4) for k, v in profile.items()},
        "optimal_plan": optimal_plan,
        "chart_data": chart_data.to_dict(orient="records"),
        "total_entries": len(df),
    }
    _analysis_cache[cache_key] = result
    return result


# --------------------------------------------------
# Routes — users
# --------------------------------------------------

@app.get("/users")
def list_users():
    users = [
        f.replace(".csv", "")
        for f in os.listdir(USERS_DIR)
        if f.endswith(".csv")
    ]
    return {"users": users}


@app.get("/users/{username}/analysis")
def get_analysis(username: str):
    if not user_exists(username):
        raise HTTPException(status_code=404, detail="User not found")
    if sum(1 for _ in open(get_user_file(username))) < 3:
        raise HTTPException(status_code=400, detail="Not enough data yet")
    return build_analysis(username)


# --------------------------------------------------
# Routes — entries
# --------------------------------------------------

@app.post("/entries")
def add_entry(entry: NewEntry):
    user_file = get_user_file(entry.username)

    if os.path.exists(user_file):
        df = pd.read_csv(user_file)
    else:
        df = pd.DataFrame()

    new_row = pd.DataFrame([{
        "date": entry.date,
        "sleep_hours": entry.sleep_hours,
        "study_hours": entry.study_hours,
        "training_hours": entry.training_hours,
        "stress": entry.stress,
        "fatigue": entry.fatigue,
        "productivity": entry.productivity,
    }])

    df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(user_file, index=False)

    return {"message": "Entry saved", "total_entries": len(df)}


# --------------------------------------------------
# Routes — tasks
# --------------------------------------------------

@app.get("/tasks/{username}")
def get_tasks(username: str, recommended_hours: float = 4.0):
    tm = TaskManager(username, USERS_DIR)
    return {
        "tasks": tm.get_todays_tasks(),
        "progress": tm.get_progress(recommended_hours),
    }


@app.post("/tasks")
def add_task(task: NewTask):
    tm = TaskManager(task.username, USERS_DIR)
    new_task = tm.add_task(task.name, task.hours, task.carry_over, task.category)
    return new_task


@app.post("/tasks/complete")
def complete_task(action: TaskAction):
    tm = TaskManager(action.username, USERS_DIR)
    try:
        updated = tm.complete_task(action.task_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tasks/uncomplete")
def uncomplete_task(action: TaskAction):
    tm = TaskManager(action.username, USERS_DIR)
    try:
        updated = tm.uncomplete_task(action.task_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/tasks/{username}/{task_id}")
def delete_task(username: str, task_id: str):
    tm = TaskManager(username, USERS_DIR)
    try:
        tm.delete_task(task_id)
        return {"message": "Task deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/tasks/toggle-carry-over")
def toggle_carry_over(action: TaskAction):
    tm = TaskManager(action.username, USERS_DIR)
    try:
        updated = tm.toggle_carry_over(action.task_id)
        return updated
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/users/{username}/entries")
def get_entries(username: str):
    if not user_exists(username):
        raise HTTPException(status_code=404, detail="User not found")
    df = pd.read_csv(get_user_file(username))
    df['date'] = df['date'].astype(str)
    return {"entries": df.to_dict(orient="records")}


@app.get("/tasks/{username}/history")
def get_task_history(username: str):
    tm = TaskManager(username, USERS_DIR)
    return {"history": tm.get_completion_history()}


@app.get("/tasks/{username}/prefill")
def get_prefill(username: str):
    """
    Returns today's completed task hours by category so the log entry
    form can pre-fill study and training hours automatically.
    """
    tm = TaskManager(username, USERS_DIR)
    hours = tm.get_todays_hours_by_category()
    total_free = None
    if user_exists(username):
        try:
            import pandas as pd
            df = pd.read_csv(get_user_file(username))
            if not df.empty:
                last = df.iloc[-1]
                logged = float(last.get("sleep_hours", 0)) + float(last.get("study_hours", 0)) + float(last.get("training_hours", 0))
                total_free = round(max(0, 24 - logged), 2)
        except Exception:
            pass
    return {"hours_by_category": hours, "free_hours_yesterday": total_free}