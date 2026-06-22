from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List


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
        self.is_complete = True


@dataclass
class Pet:
    name: str
    breed: str
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)

    def remove_task(self, task: Task) -> None:
        self.tasks.remove(task)

    def sort_tasks(self) -> None:
        self.tasks.sort(key=lambda t: PRIORITY_ORDER.get(t.priority, 99))


@dataclass
class Scheduler:
    pet: Pet
    owner: Owner

    def sort_by_priority(self) -> List[Task]:
        return sorted(self.pet.tasks, key=lambda t: PRIORITY_ORDER.get(t.priority, 99))

    def fit_tasks_by_time(self) -> List[Task]:
        plan: List[Task] = []
        time_remaining = self.owner.available_minutes
        for task in self.sort_by_priority():
            if task.duration_minutes <= time_remaining:
                plan.append(task)
                time_remaining -= task.duration_minutes
        return plan

    def generate_plan(self) -> List[Task]:
        return self.fit_tasks_by_time()

    def mark_task_done(self, task: Task) -> None:
        task.mark_complete()
