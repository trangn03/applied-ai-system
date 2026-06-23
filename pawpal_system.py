from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Recurrence(str, Enum):
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"


PRIORITY_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}

# How far ahead the next occurrence of a recurring task falls.
RECURRENCE_STEP = {Recurrence.DAILY: timedelta(days=1), Recurrence.WEEKLY: timedelta(weeks=1)}


def parse_hhmm(value: str) -> int:
    """Convert a 'HH:MM' string to minutes from midnight."""
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def format_minutes(minutes: int) -> str:
    """Format minutes-from-midnight as a 24-hour HH:MM string."""
    minutes %= 24 * 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def same_day(a: Task, b: Task) -> bool:
    """True if two tasks fall on the same day (both undated counts as same)."""
    return a.due_date == b.due_date


def tasks_overlap(a: Task, b: Task) -> bool:
    """True if two tasks share a day and their time spans intersect.

    Touching ends don't count, and occurrences on different dates never
    overlap even when their times of day coincide (e.g. a daily 09:00 walk).
    """
    return (
        same_day(a, b)
        and a.start_minutes < b.end_minutes
        and b.start_minutes < a.end_minutes
    )


@dataclass
class Owner:
    name: str
    available_minutes: int
    requested_services: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "available_minutes": self.available_minutes,
            "requested_services": self.requested_services,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Owner":
        return cls(
            name=data["name"],
            available_minutes=data["available_minutes"],
            requested_services=data.get("requested_services", ""),
        )


@dataclass
class Task:
    title: str
    duration_minutes: int
    priority: Priority
    start_time: str = "08:00"  # 24-hour "HH:MM"
    is_complete: bool = False
    recurrence: Recurrence = Recurrence.NONE
    due_date: Optional[date] = None  # the day this occurrence is scheduled for

    @property
    def start_minutes(self) -> int:
        """Start time as minutes from midnight (parsed from the HH:MM string)."""
        return parse_hhmm(self.start_time)

    @property
    def end_minutes(self) -> int:
        """Minute-of-day at which this task finishes."""
        return self.start_minutes + self.duration_minutes

    @property
    def is_recurring(self) -> bool:
        return self.recurrence != Recurrence.NONE

    def mark_complete(self) -> None:
        """Mark this task as completed."""
        self.is_complete = True

    def next_occurrence(self, today: Optional[date] = None) -> Optional["Task"]:
        """Build the next pending instance of a recurring task.

        Returns a fresh, incomplete copy with its due_date advanced by one day
        (daily) or one week (weekly). Returns None for non-recurring tasks.
        """
        step = RECURRENCE_STEP.get(self.recurrence)
        if step is None:
            return None
        base = self.due_date or today or date.today()
        return replace(self, is_complete=False, due_date=base + step)

    def to_dict(self) -> dict:
        """Serialize to plain JSON-friendly types (enums -> str, date -> ISO)."""
        return {
            "title": self.title,
            "duration_minutes": self.duration_minutes,
            "priority": self.priority.value,
            "start_time": self.start_time,
            "is_complete": self.is_complete,
            "recurrence": self.recurrence.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Rebuild a Task from the dict produced by to_dict()."""
        due = data.get("due_date")
        return cls(
            title=data["title"],
            duration_minutes=data["duration_minutes"],
            priority=Priority(data["priority"]),
            start_time=data.get("start_time", "08:00"),
            is_complete=data.get("is_complete", False),
            recurrence=Recurrence(data.get("recurrence", "none")),
            due_date=date.fromisoformat(due) if due else None,
        )


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

    def update_task(self, task: Task, **changes) -> None:
        """Apply field updates to an existing task in-place using dataclass replace."""
        idx = self.tasks.index(task)
        self.tasks[idx] = replace(task, **changes)

    def complete_task(self, task: Task, today: Optional[date] = None) -> Optional[Task]:
        """Mark a task complete and, if it recurs, queue its next occurrence.

        Returns the newly created next-occurrence task, or None if the task
        does not recur. Idempotent: completing an already-complete task is a
        no-op and never queues a duplicate occurrence.
        """
        if task.is_complete:
            return None
        task.mark_complete()
        next_task = task.next_occurrence(today=today)
        if next_task is not None:
            self.add_task(next_task)
        return next_task

    def filter_tasks(
        self,
        *,
        complete: bool | None = None,
        priority: Priority | None = None,
    ) -> List[Task]:
        """Return tasks matching the given criteria, preserving current order.

        Any argument left as None is ignored, so callers can filter by
        completion status, priority, or both.
        """
        return [
            t
            for t in self.tasks
            if (complete is None or t.is_complete == complete)
            and (priority is None or t.priority == priority)
        ]

    def pending(self) -> List[Task]:
        """Convenience: tasks that are not yet complete."""
        return self.filter_tasks(complete=False)

    def sort_tasks(self) -> None:
        """Sort tasks in-place by start time, then priority, then duration.

        Same-slot ties break toward higher priority, and equal-priority ties
        toward the shorter task. Python's sort is stable, so this single
        multi-key pass is deterministic and runs in O(n log n).
        """
        self.tasks.sort(
            key=lambda t: (
                tuple(map(int, t.start_time.split(":"))),
                PRIORITY_ORDER.get(t.priority, 99),
                t.duration_minutes,
            )
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "breed": self.breed,
            "tasks": [t.to_dict() for t in self.tasks],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Pet":
        return cls(
            name=data["name"],
            breed=data.get("breed", ""),
            tasks=[Task.from_dict(t) for t in data.get("tasks", [])],
        )


@dataclass
class Scheduler:
    pet: Pet
    owner: Owner

    def sort_by_priority(self) -> List[Task]:
        """Return tasks sorted from highest to lowest priority without mutating the list."""
        return sorted(self.pet.tasks, key=lambda t: PRIORITY_ORDER.get(t.priority, 99))

    def sort_by_time(self) -> List[Task]:
        """Return tasks ordered by start time (earliest first) without mutating the list.

        Same-slot ties break toward higher priority, then the shorter task.
        """
        return sorted(
            self.pet.tasks,
            key=lambda t: (
                tuple(map(int, t.start_time.split(":"))),
                PRIORITY_ORDER.get(t.priority, 99),
                t.duration_minutes,
            ),
        )

    def find_conflicts(self) -> List[Tuple[Task, Task]]:
        """Return pairs of this pet's pending tasks whose time spans overlap.

        Tasks are swept in start-time order, so once a later task starts after
        the current one ends we stop comparing — close to O(n) for the typical
        sparse day rather than O(n^2).
        """
        ordered = sorted(self.pet.pending(), key=lambda t: t.start_minutes)
        conflicts: List[Tuple[Task, Task]] = []
        for i, earlier in enumerate(ordered):
            for later in ordered[i + 1 :]:
                if later.start_minutes >= earlier.end_minutes:
                    break  # sorted by start: nothing after this can overlap `earlier`
                if tasks_overlap(earlier, later):
                    conflicts.append((earlier, later))
        return conflicts

    @staticmethod
    def find_conflicts_among(pets: List[Pet]) -> List[Tuple[Pet, Task, Pet, Task]]:
        """Return overlapping pending tasks across pets (the owner can't be in two
        places at once). Pairs from the same pet are included too.

        Each result is (pet_a, task_a, pet_b, task_b) ordered by start time.
        """
        items: List[Tuple[Pet, Task]] = [
            (pet, task) for pet in pets for task in pet.pending()
        ]
        items.sort(key=lambda pt: pt[1].start_minutes)
        conflicts: List[Tuple[Pet, Task, Pet, Task]] = []
        for i, (pet_a, task_a) in enumerate(items):
            for pet_b, task_b in items[i + 1 :]:
                if task_b.start_minutes >= task_a.end_minutes:
                    break
                if tasks_overlap(task_a, task_b):
                    conflicts.append((pet_a, task_a, pet_b, task_b))
        return conflicts

    def fit_tasks_by_time(self) -> List[Task]:
        """Return the highest-priority pending tasks that fit within the owner's time.

        A task is added only if it both fits the remaining budget and does not
        overlap a task already chosen, so the plan is always conflict-free.
        Higher-priority tasks are considered first, so when two tasks clash the
        more important one wins the slot.
        """
        plan: List[Task] = []
        time_remaining = self.owner.available_minutes
        pending = self.pet.pending()
        for task in sorted(pending, key=lambda t: PRIORITY_ORDER.get(t.priority, 99)):
            if task.duration_minutes > time_remaining:
                continue
            if any(tasks_overlap(task, chosen) for chosen in plan):
                continue
            plan.append(task)
            time_remaining -= task.duration_minutes
        return plan

    def generate_plan(self) -> List[Task]:
        """Generate the recommended task plan for the current pet and owner."""
        return self.fit_tasks_by_time()

    @staticmethod
    def generate_owner_plan(
        pets: List[Pet], owner: Owner
    ) -> List[Tuple[Pet, Task]]:
        """Build one conflict-free plan across all of an owner's pets.

        The owner has a single time budget and can only attend one pet at a
        time, so tasks from every pet compete for the same minutes. Tasks are
        considered highest-priority first (ties broken by start time so the day
        reads in order); each is added only if it fits the remaining budget and
        does not overlap a task already chosen for any pet.

        Returns the chosen (pet, task) pairs ordered by start time.
        """
        candidates: List[Tuple[Pet, Task]] = [
            (pet, task) for pet in pets for task in pet.pending()
        ]
        candidates.sort(
            key=lambda pt: (
                PRIORITY_ORDER.get(pt[1].priority, 99),
                pt[1].start_minutes,
            )
        )

        plan: List[Tuple[Pet, Task]] = []
        time_remaining = owner.available_minutes
        for pet, task in candidates:
            if task.duration_minutes > time_remaining:
                continue
            if any(tasks_overlap(task, chosen) for _, chosen in plan):
                continue
            plan.append((pet, task))
            time_remaining -= task.duration_minutes

        plan.sort(key=lambda pt: pt[1].start_minutes)
        return plan

    def mark_task_done(self, task: Task) -> Optional[Task]:
        """Mark the given task complete, queuing its next occurrence if recurring."""
        return self.pet.complete_task(task)


# --- Persistence ---------------------------------------------------------

SCHEMA_VERSION = 1


def serialize_state(owner: Optional[Owner], pets: Dict[str, Pet]) -> dict:
    """Build a JSON-ready snapshot of the whole app state.

    `owner` may be None (not yet saved). `pets` is the name -> Pet registry.
    """
    return {
        "version": SCHEMA_VERSION,
        "owner": owner.to_dict() if owner else None,
        "pets": [pet.to_dict() for pet in pets.values()],
    }


def deserialize_state(data: dict) -> Tuple[Optional[Owner], Dict[str, Pet]]:
    """Rebuild (owner, pets-registry) from a serialize_state() snapshot.

    Unknown future versions still load on a best-effort basis. Returns the
    owner (or None) and a name -> Pet dict in file order.
    """
    owner_data = data.get("owner")
    owner = Owner.from_dict(owner_data) if owner_data else None
    pets: Dict[str, Pet] = {}
    for pet_data in data.get("pets", []):
        pet = Pet.from_dict(pet_data)
        pets[pet.name] = pet
    return owner, pets
