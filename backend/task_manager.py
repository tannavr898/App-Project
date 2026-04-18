import uuid
from datetime import date

from data_store import (
    apply_task_carry_over,
    delete_task,
    ensure_database,
    get_completion_history,
    get_today_category_hours,
    get_todays_tasks,
    get_task,
    set_task_completed,
    toggle_task_carry_over,
    upsert_task,
)


class TaskManager:
    def __init__(self, username: str, users_dir: str = "users"):
        self.username = username
        ensure_database()
        self._apply_carry_over()

    def _today(self) -> str:
        return date.today().isoformat()

    def _apply_carry_over(self):
        apply_task_carry_over(self.username)

    # --------------------------------------------------
    def add_task(self, name: str, hours: float,
                 carry_over: bool = False,
                 category: str = "other") -> dict:
        if hours <= 0:
            raise ValueError("Task hours must be greater than 0.")
        if not name.strip():
            raise ValueError("Task name cannot be empty.")

        valid_categories = {"study", "training", "personal", "other"}
        if category not in valid_categories:
            category = "other"

        task = {
            "id": str(uuid.uuid4())[:8],
            "name": name.strip(),
            "hours": round(hours, 2),
            "category": category,
            "completed": False,
            "carry_over": carry_over,
            "date_created": self._today(),
            "date_completed": None,
        }
        upsert_task(self.username, task)
        return task

    def complete_task(self, task_id: str) -> dict:
        task = set_task_completed(self.username, task_id, True)
        if task is None:
            raise ValueError(f"Task with id '{task_id}' not found.")
        return task

    def uncomplete_task(self, task_id: str) -> dict:
        task = set_task_completed(self.username, task_id, False)
        if task is None:
            raise ValueError(f"Task with id '{task_id}' not found.")
        return task

    def delete_task(self, task_id: str):
        task = get_task(self.username, task_id)
        if task is None:
            raise ValueError(f"Task with id '{task_id}' not found.")
        delete_task(self.username, task_id)

    def toggle_carry_over(self, task_id: str) -> dict:
        task = toggle_task_carry_over(self.username, task_id)
        if task is None:
            raise ValueError(f"Task with id '{task_id}' not found.")
        return task

    def get_todays_tasks(self) -> list:
        return get_todays_tasks(self.username)

    def get_progress(self, recommended_hours: float) -> dict:
        todays = self.get_todays_tasks()
        completed_hours = sum(t["hours"] for t in todays if t["completed"])
        total_hours     = sum(t["hours"] for t in todays)

        if recommended_hours <= 0:
            progress_pct = 100.0
        else:
            progress_pct = min(100.0, (completed_hours / recommended_hours) * 100)

        return {
            "completed_hours":   round(completed_hours, 2),
            "total_hours":       round(total_hours, 2),
            "recommended":       round(recommended_hours, 2),
            "progress_pct":      round(progress_pct, 1),
            "remaining_hours":   round(max(0.0, recommended_hours - completed_hours), 2),
            "on_track":          completed_hours >= recommended_hours,
        }

    def get_todays_hours_by_category(self) -> dict:
        """
        Returns completed hours broken down by category for today.
        Used to pre-fill the log entry form.
        """
        return get_today_category_hours(self.username)

    def get_completion_history(self) -> dict:
        return get_completion_history(self.username)