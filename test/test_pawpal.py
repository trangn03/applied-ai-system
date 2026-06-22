import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pawpal_system import Task, Pet, Priority


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
