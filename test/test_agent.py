import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import json

import agent
from agent import AgentUnavailable
from pawpal_system import Owner, Pet, Task, Priority


def make_pet(name, title, duration, priority, start_time):
    pet = Pet(name=name, breed="Mixed")
    pet.add_task(Task(title=title, duration_minutes=duration, priority=priority, start_time=start_time))
    return pet


# --- suggest_priority_overrides ---------------------------------------------

def test_suggest_priority_overrides_returns_empty_without_calling_agent_when_no_pending_tasks(monkeypatch):
    calls = []
    monkeypatch.setattr(agent, "_call", lambda system, user: calls.append(1) or "{}")

    owner = Owner(name="Alex", available_minutes=60)
    pet = Pet(name="Buddy", breed="Mixed")  # no tasks

    result = agent.suggest_priority_overrides([pet], owner)

    assert result == {}
    assert calls == []  # never worth spending an API call on nothing


def test_suggest_priority_overrides_filters_unknown_keys_and_invalid_priorities(monkeypatch):
    pet = make_pet("Buddy", "Brush coat", 20, Priority.LOW, "12:00")
    owner = Owner(name="Alex", available_minutes=60)

    raw = json.dumps({
        "Buddy::Brush coat": "high",       # valid
        "Buddy::Nonexistent task": "high",  # unknown task -> dropped
        "Buddy::Brush coat2": "urgent",     # invalid priority value -> dropped
    })
    monkeypatch.setattr(agent, "_call", lambda system, user: raw)

    result = agent.suggest_priority_overrides([pet], owner)

    assert result == {"Buddy::Brush coat": "high"}


def test_suggest_priority_overrides_returns_empty_when_agent_unavailable(monkeypatch):
    pet = make_pet("Buddy", "Walk", 20, Priority.LOW, "09:00")
    owner = Owner(name="Alex", available_minutes=60)

    def boom(system, user):
        raise AgentUnavailable("no key")

    monkeypatch.setattr(agent, "_call", boom)

    assert agent.suggest_priority_overrides([pet], owner) == {}


def test_suggest_priority_overrides_returns_empty_on_malformed_json(monkeypatch):
    pet = make_pet("Buddy", "Walk", 20, Priority.LOW, "09:00")
    owner = Owner(name="Alex", available_minutes=60)

    monkeypatch.setattr(agent, "_call", lambda system, user: "not json")

    assert agent.suggest_priority_overrides([pet], owner) == {}


# --- generate_plan (Plan -> Act -> Check -> Revise) -------------------------

def test_generate_plan_falls_back_when_agent_suggests_nothing(monkeypatch):
    pet = make_pet("Buddy", "Walk", 20, Priority.LOW, "09:00")
    owner = Owner(name="Alex", available_minutes=60)

    monkeypatch.setattr(agent, "_call", lambda system, user: "{}")

    plan, used_agent = agent.generate_plan([pet], owner)

    assert used_agent is False
    assert [t.title for _, t in plan] == ["Walk"]


def test_generate_plan_applies_a_valid_override(monkeypatch):
    # Two overlapping tasks on the SAME pet: whichever is higher priority wins
    # the shared slot. "Vet visit" starts LOW, so the plain scheduler picks
    # "Grooming"; an override bumping "Vet visit" should flip that outcome.
    # (Single pet, so either choice still counts as "not starved" -- this
    # isolates the override's effect from the starvation-revert safeguard.)
    buddy = Pet(name="Buddy", breed="Mixed")
    buddy.add_task(Task(title="Vet visit", duration_minutes=30, priority=Priority.LOW, start_time="09:00"))
    buddy.add_task(Task(title="Grooming", duration_minutes=30, priority=Priority.MEDIUM, start_time="09:00"))
    owner = Owner(name="Alex", available_minutes=30)

    override = json.dumps({"Buddy::Vet visit": "high"})
    monkeypatch.setattr(agent, "_call", lambda system, user: override)

    plan, used_agent = agent.generate_plan([buddy], owner)

    assert used_agent is True
    assert [(p.name, t.title) for p, t in plan] == [("Buddy", "Vet visit")]
    # the saved tasks themselves must be untouched -- overrides are run-scoped only
    assert buddy.tasks[0].priority == Priority.LOW


def test_generate_plan_reverts_when_override_cannot_avoid_starvation(monkeypatch):
    # Same clash as above, but the override targets the pet that's already
    # going to lose the slot either way -- no override can prevent someone
    # from being starved, so generate_plan should give up and revert cleanly
    # to the plain, unmodified scheduler rather than keep an unhelpful override.
    buddy = make_pet("Buddy", "Vet visit", 30, Priority.HIGH, "09:00")
    whiskers = make_pet("Whiskers", "Grooming", 30, Priority.LOW, "09:00")
    owner = Owner(name="Alex", available_minutes=30)

    # Agent keeps suggesting the same no-op-ish override every round.
    override = json.dumps({"Whiskers::Grooming": "medium"})
    monkeypatch.setattr(agent, "_call", lambda system, user: override)

    plan, used_agent = agent.generate_plan([buddy, whiskers], owner)

    plain_plan = agent.Scheduler.generate_owner_plan([buddy, whiskers], owner)
    assert used_agent is False
    assert [(p.name, t.title) for p, t in plan] == [(p.name, t.title) for p, t in plain_plan]


# --- explain_plan ------------------------------------------------------------

def test_explain_plan_returns_text_that_references_a_known_task(monkeypatch):
    pet = make_pet("Buddy", "Walk", 20, Priority.HIGH, "09:00")
    owner = Owner(name="Alex", available_minutes=60)
    plan = [(pet, pet.tasks[0])]

    monkeypatch.setattr(agent, "_call", lambda system, user: "Buddy's Walk is scheduled at 9am, enjoy!")

    explanation = agent.explain_plan(plan, [], owner)

    assert "Walk" in explanation


def test_explain_plan_rejects_ungrounded_response(monkeypatch):
    pet = make_pet("Buddy", "Walk", 20, Priority.HIGH, "09:00")
    owner = Owner(name="Alex", available_minutes=60)
    plan = [(pet, pet.tasks[0])]

    # Hallucinated response that never mentions the actual scheduled task.
    monkeypatch.setattr(agent, "_call", lambda system, user: "Your cat's grooming session went great!")

    try:
        agent.explain_plan(plan, [], owner)
        assert False, "expected AgentUnavailable for an ungrounded explanation"
    except AgentUnavailable:
        pass