import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import date

import pytest

from pawpal_system import (
    Task,
    Pet,
    Priority,
    Recurrence,
    Owner,
    Scheduler,
    format_minutes,
    serialize_state,
    deserialize_state,
)


def test_mark_complete_changes_status():
    task = Task(title="Feed", duration_minutes=5, priority=Priority.HIGH)
    assert task.is_complete is False
    task.mark_complete()
    assert task.is_complete is True


def test_add_task_increases_pet_task_count():
    pet = Pet(name="Buddy", breed="Labrador")
    assert len(pet.tasks) == 0
    pet.add_task(Task(title="Walk", duration_minutes=30, priority=Priority.MEDIUM))
    assert len(pet.tasks) == 1


def test_generate_plan_skips_conflicting_tasks():
    """Two overlapping tasks can't both be scheduled; the higher priority wins."""
    pet = Pet(name="Buddy", breed="Labrador")
    pet.add_task(Task(title="Walk", duration_minutes=30, priority=Priority.HIGH, start_time="09:00"))
    pet.add_task(Task(title="Vet call", duration_minutes=20, priority=Priority.LOW, start_time="09:10"))
    owner = Owner(name="Alex", available_minutes=120)

    plan = Scheduler(pet=pet, owner=owner).generate_plan()

    titles = [t.title for t in plan]
    assert titles == ["Walk"]  # "Vet call" overlaps and loses on priority


def test_generate_plan_keeps_non_overlapping_tasks():
    """Tasks that don't overlap and fit in budget are all scheduled."""
    pet = Pet(name="Buddy", breed="Labrador")
    pet.add_task(Task(title="Walk", duration_minutes=30, priority=Priority.HIGH, start_time="09:00"))
    pet.add_task(Task(title="Vet call", duration_minutes=20, priority=Priority.LOW, start_time="10:00"))
    owner = Owner(name="Alex", available_minutes=120)

    plan = Scheduler(pet=pet, owner=owner).generate_plan()

    assert {t.title for t in plan} == {"Walk", "Vet call"}


def test_owner_plan_avoids_cross_pet_double_booking():
    """Two pets' tasks overlap; the owner can only do one, so the lower wins is dropped."""
    buddy = Pet(name="Buddy", breed="Lab")
    buddy.add_task(Task(title="Buddy walk", duration_minutes=30, priority=Priority.HIGH, start_time="09:00"))
    whiskers = Pet(name="Whiskers", breed="Cat")
    whiskers.add_task(Task(title="Whiskers groom", duration_minutes=20, priority=Priority.LOW, start_time="09:10"))
    owner = Owner(name="Alex", available_minutes=120)

    plan = Scheduler.generate_owner_plan([buddy, whiskers], owner)

    chosen = [(p.name, t.title) for p, t in plan]
    assert chosen == [("Buddy", "Buddy walk")]  # higher-priority Buddy task wins the slot


def test_owner_plan_shares_one_time_budget():
    """The owner's minutes are shared across pets, not granted per pet."""
    buddy = Pet(name="Buddy", breed="Lab")
    buddy.add_task(Task(title="Buddy walk", duration_minutes=40, priority=Priority.HIGH, start_time="09:00"))
    whiskers = Pet(name="Whiskers", breed="Cat")
    whiskers.add_task(Task(title="Whiskers play", duration_minutes=40, priority=Priority.LOW, start_time="11:00"))
    owner = Owner(name="Alex", available_minutes=50)  # only one 40-min task fits

    plan = Scheduler.generate_owner_plan([buddy, whiskers], owner)

    assert [t.title for _, t in plan] == ["Buddy walk"]


def test_state_round_trips_through_serialization():
    """serialize_state -> deserialize_state preserves owner, pets, and task fields."""
    buddy = Pet(name="Buddy", breed="Lab")
    buddy.add_task(
        Task(
            title="Morning walk",
            duration_minutes=30,
            priority=Priority.HIGH,
            start_time="07:30",
            is_complete=True,
            recurrence=Recurrence.DAILY,
            due_date=date(2026, 6, 23),
        )
    )
    owner = Owner(name="Alex", available_minutes=90)

    data = serialize_state(owner, {"Buddy": buddy})
    restored_owner, restored_pets = deserialize_state(data)

    assert restored_owner.name == "Alex"
    assert restored_owner.available_minutes == 90
    task = restored_pets["Buddy"].tasks[0]
    assert task.title == "Morning walk"
    assert task.priority is Priority.HIGH
    assert task.recurrence is Recurrence.DAILY
    assert task.is_complete is True
    assert task.due_date == date(2026, 6, 23)


def test_deserialize_handles_missing_owner():
    """A snapshot saved before the owner was set still loads (owner is None)."""
    data = serialize_state(None, {})
    owner, pets = deserialize_state(data)
    assert owner is None
    assert pets == {}


# --- Required: sorting correctness ---------------------------------------

def test_sort_by_time_returns_chronological_order():
    """sort_by_time orders tasks earliest start first, regardless of insertion order."""
    pet = Pet(name="Buddy", breed="Lab")
    pet.add_task(Task(title="Evening walk", duration_minutes=30, priority=Priority.LOW, start_time="18:00"))
    pet.add_task(Task(title="Breakfast", duration_minutes=10, priority=Priority.HIGH, start_time="07:00"))
    pet.add_task(Task(title="Lunch", duration_minutes=15, priority=Priority.MEDIUM, start_time="12:00"))
    owner = Owner(name="Alex", available_minutes=240)

    ordered = Scheduler(pet=pet, owner=owner).sort_by_time()

    assert [t.title for t in ordered] == ["Breakfast", "Lunch", "Evening walk"]
    starts = [t.start_minutes for t in ordered]
    assert starts == sorted(starts)


def test_sort_tasks_breaks_same_time_ties_by_priority_then_duration():
    """Equal start times fall back to higher priority, then shorter duration."""
    pet = Pet(name="Buddy", breed="Lab")
    pet.add_task(Task(title="Low long", duration_minutes=60, priority=Priority.LOW, start_time="09:00"))
    pet.add_task(Task(title="High", duration_minutes=30, priority=Priority.HIGH, start_time="09:00"))
    pet.add_task(Task(title="Med short", duration_minutes=10, priority=Priority.MEDIUM, start_time="09:00"))

    pet.sort_tasks()

    assert [t.title for t in pet.tasks] == ["High", "Med short", "Low long"]


# --- Required: recurrence logic ------------------------------------------

def test_completing_daily_task_creates_next_day_occurrence():
    """Marking a daily task complete queues a fresh, pending copy due the next day."""
    pet = Pet(name="Buddy", breed="Lab")
    task = Task(
        title="Morning walk",
        duration_minutes=30,
        priority=Priority.HIGH,
        start_time="07:00",
        recurrence=Recurrence.DAILY,
        due_date=date(2026, 6, 22),
    )
    pet.add_task(task)

    next_task = pet.complete_task(task)

    assert task.is_complete is True
    assert next_task is not None
    assert next_task.is_complete is False
    assert next_task.due_date == date(2026, 6, 23)
    assert next_task.recurrence is Recurrence.DAILY
    # The new occurrence is now tracked on the pet alongside the completed one.
    assert next_task in pet.tasks


def test_completing_weekly_task_advances_due_date_by_one_week():
    pet = Pet(name="Buddy", breed="Lab")
    task = Task(
        title="Bath",
        duration_minutes=45,
        priority=Priority.MEDIUM,
        recurrence=Recurrence.WEEKLY,
        due_date=date(2026, 6, 22),
    )
    pet.add_task(task)

    next_task = pet.complete_task(task)

    assert next_task.due_date == date(2026, 6, 29)


def test_completing_non_recurring_task_creates_no_followup():
    pet = Pet(name="Buddy", breed="Lab")
    task = Task(title="Vet visit", duration_minutes=30, priority=Priority.HIGH)
    pet.add_task(task)

    next_task = pet.complete_task(task)

    assert next_task is None
    assert len(pet.tasks) == 1


# --- Required: conflict detection ----------------------------------------

def test_find_conflicts_flags_overlapping_times():
    """Two pending tasks sharing the same slot are reported as a conflict."""
    pet = Pet(name="Buddy", breed="Lab")
    walk = Task(title="Walk", duration_minutes=30, priority=Priority.HIGH, start_time="09:00")
    feed = Task(title="Feed", duration_minutes=20, priority=Priority.LOW, start_time="09:00")
    pet.add_task(walk)
    pet.add_task(feed)
    owner = Owner(name="Alex", available_minutes=120)

    conflicts = Scheduler(pet=pet, owner=owner).find_conflicts()

    assert len(conflicts) == 1
    assert {t.title for t in conflicts[0]} == {"Walk", "Feed"}


def test_find_conflicts_ignores_touching_but_non_overlapping_tasks():
    """A task ending exactly when the next begins is not a conflict."""
    pet = Pet(name="Buddy", breed="Lab")
    pet.add_task(Task(title="Walk", duration_minutes=30, priority=Priority.HIGH, start_time="09:00"))
    pet.add_task(Task(title="Feed", duration_minutes=15, priority=Priority.LOW, start_time="09:30"))
    owner = Owner(name="Alex", available_minutes=120)

    assert Scheduler(pet=pet, owner=owner).find_conflicts() == []


# --- Edge cases flagged as likely bugs -----------------------------------

def test_completing_task_twice_does_not_double_queue():
    """Completing an already-complete task should not spawn a second occurrence.

    Documents the expected idempotent behavior; currently complete_task has no
    guard and will queue a duplicate on the second call.
    """
    pet = Pet(name="Buddy", breed="Lab")
    task = Task(
        title="Morning walk",
        duration_minutes=30,
        priority=Priority.HIGH,
        recurrence=Recurrence.DAILY,
        due_date=date(2026, 6, 22),
    )
    pet.add_task(task)

    pet.complete_task(task)
    pet.complete_task(task)

    next_occurrences = [t for t in pet.tasks if not t.is_complete]
    assert len(next_occurrences) == 1


def test_conflict_detection_respects_due_date_across_days():
    """Same-time tasks on different days must not be flagged as conflicting.

    find_conflicts compares only start_minutes, so two daily occurrences on
    different dates currently collide even though they never coincide.
    """
    pet = Pet(name="Buddy", breed="Lab")
    pet.add_task(Task(
        title="Walk Mon", duration_minutes=30, priority=Priority.HIGH,
        start_time="09:00", recurrence=Recurrence.DAILY, due_date=date(2026, 6, 22),
    ))
    pet.add_task(Task(
        title="Walk Tue", duration_minutes=30, priority=Priority.HIGH,
        start_time="09:00", recurrence=Recurrence.DAILY, due_date=date(2026, 6, 23),
    ))
    owner = Owner(name="Alex", available_minutes=120)

    assert Scheduler(pet=pet, owner=owner).find_conflicts() == []


# --- Input validation ----------------------------------------------------

def test_task_rejects_nonpositive_duration():
    """A zero- or negative-length task is bad data and must be refused."""
    with pytest.raises(ValueError):
        Task(title="Ghost task", duration_minutes=0, priority=Priority.LOW)
    with pytest.raises(ValueError):
        Task(title="Negative", duration_minutes=-5, priority=Priority.LOW)


def test_task_rejects_malformed_start_time():
    """start_time must be a real HH:MM in the 00:00-23:59 range."""
    for bad in ["25:00", "09:60", "9am", "noon", ""]:
        with pytest.raises(ValueError):
            Task(title="Bad time", duration_minutes=10, priority=Priority.LOW, start_time=bad)


def test_owner_rejects_negative_available_minutes():
    with pytest.raises(ValueError):
        Owner(name="Alex", available_minutes=-30)


def test_owner_with_zero_minutes_schedules_nothing():
    """Zero available minutes is valid and yields an empty (not crashing) plan."""
    pet = Pet(name="Buddy", breed="Lab")
    pet.add_task(Task(title="Walk", duration_minutes=20, priority=Priority.HIGH, start_time="09:00"))
    owner = Owner(name="Alex", available_minutes=0)

    assert Scheduler(pet=pet, owner=owner).generate_plan() == []


# --- Recurrence across calendar boundaries -------------------------------

def test_recurrence_steps_across_month_boundary():
    """A daily task due on the last of the month rolls to the first of the next."""
    task = Task(
        title="Walk", duration_minutes=30, priority=Priority.HIGH,
        recurrence=Recurrence.DAILY, due_date=date(2026, 6, 30),
    )
    assert task.next_occurrence().due_date == date(2026, 7, 1)


def test_recurrence_steps_across_leap_day():
    """A daily task due Feb 28 in a leap year advances to Feb 29, not Mar 1."""
    task = Task(
        title="Walk", duration_minutes=30, priority=Priority.HIGH,
        recurrence=Recurrence.DAILY, due_date=date(2024, 2, 28),
    )
    assert task.next_occurrence().due_date == date(2024, 2, 29)


def test_recurrence_steps_across_year_boundary():
    """A weekly task near year-end advances by seven days into January."""
    task = Task(
        title="Bath", duration_minutes=45, priority=Priority.MEDIUM,
        recurrence=Recurrence.WEEKLY, due_date=date(2026, 12, 29),
    )
    assert task.next_occurrence().due_date == date(2027, 1, 5)


def test_overdue_daily_task_catches_up_to_today():
    """Completing a long-overdue daily task requeues it for today, not the past."""
    task = Task(
        title="Walk", duration_minutes=30, priority=Priority.HIGH,
        recurrence=Recurrence.DAILY, due_date=date(2026, 6, 22),
    )
    # due_date is 5 days behind the reference "today"
    nxt = task.next_occurrence(today=date(2026, 6, 27))
    assert nxt.due_date == date(2026, 6, 27)
    assert nxt.is_complete is False


def test_next_occurrence_without_today_advances_exactly_one_step():
    """With no reference date, behavior is unchanged: one step past due_date."""
    task = Task(
        title="Walk", duration_minutes=30, priority=Priority.HIGH,
        recurrence=Recurrence.DAILY, due_date=date(2026, 6, 22),
    )
    assert task.next_occurrence().due_date == date(2026, 6, 23)


# --- Time-of-day boundaries ----------------------------------------------

def test_late_task_end_minutes_extend_past_midnight_and_display_wraps():
    """A late task's end runs past 24:00 in raw minutes but displays wrapped.

    Documents the current (day-local) model: end_minutes is not wrapped, so
    overlap math stays monotonic within a single day, while format_minutes
    wraps only for display. Both behaviors are relied on elsewhere.
    """
    task = Task(title="Late walk", duration_minutes=60, priority=Priority.LOW, start_time="23:30")
    assert task.end_minutes == 23 * 60 + 30 + 60  # 1470, not wrapped
    assert format_minutes(task.end_minutes) == "00:30"  # wrapped for display
