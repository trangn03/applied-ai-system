from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}


@dataclass
class Owner:
    name: str
    available_minutes: int
    requested_services: str = ""


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: Priority
    is_complete: bool = False

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.is_complete = True


@dataclass
class Pet:
    name: str
    breed: str
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Append a task to this pet's task list."""
        self.tasks.append(task)

    def remove_task(self, task: Task) -> None:
        """Remove a task from this pet's task list."""
        self.tasks.remove(task)

    def sort_tasks(self) -> None:
        """Sort tasks in-place from highest to lowest priority."""
        self.tasks.sort(key=lambda t: PRIORITY_ORDER.get(t.priority, 99))


@dataclass
class Scheduler:
    pet: Pet
    owner: Owner

    def sort_by_priority(self) -> List[Task]:
        """Return tasks sorted from highest to lowest priority without mutating the list."""
        return sorted(self.pet.tasks, key=lambda t: PRIORITY_ORDER.get(t.priority, 99))

    def fit_tasks_by_time(self) -> List[Task]:
        """Return the highest-priority pending tasks that fit within the owner's available time."""
        plan: List[Task] = []
        time_remaining = self.owner.available_minutes
        for task in self.sort_by_priority():
            if task.is_complete:
                continue
            if task.duration_minutes <= time_remaining:
                plan.append(task)
                time_remaining -= task.duration_minutes
        return plan

    def generate_plan(self) -> List[Task]:
        """Generate the recommended task plan for the current pet and owner."""
        return self.fit_tasks_by_time()

    def mark_task_done(self, task: Task) -> None:
        """Mark the given task as complete."""
        task.mark_complete()
