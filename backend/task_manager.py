import json
import os
import uuid
from datetime import datetime, date


class TaskManager:
    def __init__(self, username: str, users_dir: str = "users"):
        self.username = username
        self.tasks_file = os.path.join(users_dir, f"{username}_tasks.json")
        os.makedirs(users_dir, exist_ok=True)
        self.tasks = self._load()
        self._apply_carry_over()

    def _load(self) -> list:
        if not os.path.exists(self.tasks_file):
            return []
        with open(self.tasks_file, "r") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []

    def _save(self):
        with open(self.tasks_file, "w") as f:
            json.dump(self.tasks, f, indent=2)

    def _today(self) -> str:
        return date.today().isoformat()

    def _apply_carry_over(self):
        today = self._today()
        changed = False
        for task in self.tasks:
            if (not task["completed"] and task["carry_over"]
                    and task["date_created"] < today):
                task["date_created"] = today
                changed = True
        if changed:
            self._save()

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
        self.tasks.append(task)
        self._save()
        return task

    def complete_task(self, task_id: str) -> dict:
        for task in self.tasks:
            if task["id"] == task_id:
                task["completed"] = True
                task["date_completed"] = self._today()
                self._save()
                return task
        raise ValueError(f"Task with id '{task_id}' not found.")

    def uncomplete_task(self, task_id: str) -> dict:
        for task in self.tasks:
            if task["id"] == task_id:
                task["completed"] = False
                task["date_completed"] = None
                self._save()
                return task
        raise ValueError(f"Task with id '{task_id}' not found.")

    def delete_task(self, task_id: str):
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        if len(self.tasks) == original_len:
            raise ValueError(f"Task with id '{task_id}' not found.")
        self._save()

    def toggle_carry_over(self, task_id: str) -> dict:
        for task in self.tasks:
            if task["id"] == task_id:
                task["carry_over"] = not task["carry_over"]
                self._save()
                return task
        raise ValueError(f"Task with id '{task_id}' not found.")

    def get_todays_tasks(self) -> list:
        return [t for t in self.tasks if t["date_created"] == self._today()]

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
        todays = self.get_todays_tasks()
        result = {"study": 0.0, "training": 0.0, "personal": 0.0, "other": 0.0}
        for task in todays:
            if task["completed"]:
                cat = task.get("category", "other")
                if cat in result:
                    result[cat] += task["hours"]
        return {k: round(v, 2) for k, v in result.items()}

    def get_completion_history(self) -> dict:
        history = {}
        for task in self.tasks:
            d = task["date_created"]
            if d not in history:
                history[d] = {"completed": 0, "total": 0}
            history[d]["total"] += 1
            if task["completed"]:
                history[d]["completed"] += 1
        return {
            d: round(v["completed"] / v["total"], 2)
            for d, v in history.items()
            if v["total"] > 0
        }