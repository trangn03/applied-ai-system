import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import agent
import eval_agent
from pawpal_system import Owner, Pet, Priority, Task


# --- consistency_report ------------------------------------------------------

def test_consistency_report_all_identical_is_full_agreement():
    results = [{"Buddy::Vet visit": "high"}] * 4
    report = eval_agent.consistency_report(results)
    assert report["runs"] == 4
    assert report["unique_outcomes"] == 1
    assert report["agreement_rate"] == 1.0
    assert report["per_key_stability"]["Buddy::Vet visit"] == 1.0


def test_consistency_report_measures_partial_agreement():
    # 3 of 4 runs agree on the same outcome -> 75% agreement.
    results = [
        {"Buddy::Vet visit": "high"},
        {"Buddy::Vet visit": "high"},
        {"Buddy::Vet visit": "high"},
        {"Buddy::Vet visit": "medium"},
    ]
    report = eval_agent.consistency_report(results)
    assert report["unique_outcomes"] == 2
    assert report["agreement_rate"] == 0.75
    assert report["per_key_stability"]["Buddy::Vet visit"] == 0.75


def test_consistency_report_key_absent_in_some_runs_lowers_stability():
    results = [{"A": "high"}, {}, {"A": "high"}, {}]
    report = eval_agent.consistency_report(results)
    # "A" appears with "high" in 2 of 4 runs; absent in the other 2 -> tie at 0.5
    assert report["per_key_stability"]["A"] == 0.5


def test_consistency_report_handles_no_runs():
    report = eval_agent.consistency_report([])
    assert report["runs"] == 0
    assert report["agreement_rate"] == 1.0


def test_canonical_is_order_independent():
    assert eval_agent.canonical({"a": "1", "b": "2"}) == eval_agent.canonical({"b": "2", "a": "1"})


# --- plan_is_valid -----------------------------------------------------------

def _pet_with(*tasks):
    pet = Pet(name="P", breed="X")
    for t in tasks:
        pet.add_task(t)
    return pet


def test_plan_is_valid_accepts_conflict_free_in_budget_plan():
    pet = _pet_with(
        Task("Walk", 20, Priority.HIGH, start_time="09:00"),
        Task("Feed", 15, Priority.LOW, start_time="10:00"),
    )
    owner = Owner(name="Alex", available_minutes=60)
    plan = [(pet, pet.tasks[0]), (pet, pet.tasks[1])]
    assert eval_agent.plan_is_valid(plan, owner) is True


def test_plan_is_valid_rejects_over_budget_plan():
    pet = _pet_with(Task("Walk", 40, Priority.HIGH, start_time="09:00"))
    owner = Owner(name="Alex", available_minutes=30)
    assert eval_agent.plan_is_valid([(pet, pet.tasks[0])], owner) is False


def test_plan_is_valid_rejects_overlapping_plan():
    pet = _pet_with(
        Task("Walk", 30, Priority.HIGH, start_time="09:00"),
        Task("Vet", 30, Priority.LOW, start_time="09:10"),
    )
    owner = Owner(name="Alex", available_minutes=120)
    plan = [(pet, pet.tasks[0]), (pet, pet.tasks[1])]
    assert eval_agent.plan_is_valid(plan, owner) is False


# --- reliability invariant: agent plans are always valid ---------------------

def test_generate_plan_output_is_always_valid_even_with_wild_overrides(monkeypatch):
    """No matter what the LLM returns, the plan the agent hands back is valid.

    Drives generate_plan with a stub that tries to promote every task to high;
    the deterministic Scheduler must still yield a conflict-free, in-budget plan.
    """
    buddy = Pet(name="Buddy", breed="Lab")
    buddy.add_task(Task("Vet visit", 30, Priority.LOW, start_time="09:00"))
    buddy.add_task(Task("Grooming", 30, Priority.MEDIUM, start_time="09:00"))
    owner = Owner(name="Alex", available_minutes=30)

    import json as _json
    monkeypatch.setattr(
        agent, "_call",
        lambda s, u: _json.dumps({"Buddy::Vet visit": "high", "Buddy::Grooming": "high"}),
    )

    plan, _ = agent.generate_plan([buddy], owner)
    assert eval_agent.plan_is_valid(plan, owner) is True