"""Agentic layer over the deterministic Scheduler.

Scheduler.generate_owner_plan() remains the sole authority on correctness
(budget respected, no overlapping tasks) -- this module only proposes
priority tweaks before scheduling (Plan), reruns the real scheduler with
them (Act), checks whether the result looks reasonable and retries once if
not (Check/Revise), then narrates the final plan in plain language (Explain).
It never decides scheduling on its own, and any API failure degrades to the
plain scheduler output rather than breaking the app.
"""
from __future__ import annotations

import json
import os
from dataclasses import replace
from typing import Dict, List, Tuple

from pawpal_system import Owner, Pet, Priority, Scheduler, Task

MODEL = "gemini-2.5-flash"
MAX_REVISE_ROUNDS = 2


class AgentUnavailable(Exception):
    """Raised when the LLM can't be reached or returns something unusable."""


def _call(system: str, user: str) -> str:
    """Send one message to the model, raising AgentUnavailable on any failure."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise AgentUnavailable("GEMINI_API_KEY is not set.")
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=MODEL,
            contents=user,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=500,
                # These prompts are short lookups/summaries, not multi-step
                # reasoning -- without this, "thinking" tokens can eat the
                # whole max_output_tokens budget and truncate the visible text.
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        text = response.text
        if not text:
            raise AgentUnavailable("Gemini returned an empty response.")
        return text.strip()
    except AgentUnavailable:
        raise
    except Exception as exc:  # network/SDK errors -> degrade, don't crash the app
        raise AgentUnavailable(str(exc)) from exc


def _describe(pet: Pet, task: Task) -> str:
    return f"{pet.name} — {task.title} ({task.start_time}, {task.duration_minutes} min, {task.priority.value})"


def _key(pet: Pet, task: Task) -> str:
    """Composite key so two pets can have a same-titled task without colliding."""
    return f"{pet.name}::{task.title}"


# --- Plan --------------------------------------------------------------

def suggest_priority_overrides(pets: List[Pet], owner: Owner) -> Dict[str, str]:
    """Ask the agent whether any pending task's priority looks miscalibrated.

    Returns {"pet::title": new_priority}, applied only for this scheduling run --
    nothing is written back to saved task data.
    """
    pending = [(p, t) for p in pets for t in p.pending()]
    if not pending:
        return {}
    listing = "\n".join(f"- {_key(p, t)} :: {_describe(p, t)}" for p, t in pending)
    system = (
        "You prioritize pet care tasks. Only override a priority when clearly "
        "justified (e.g. a medical task under-prioritized). Respond with strict "
        'JSON mapping the "pet::title" key to "high", "medium", or "low" -- use '
        "{} if no changes are warranted. No prose, no markdown fences."
    )
    user = f"Owner has {owner.available_minutes} minutes today.\nTasks:\n{listing}"
    try:
        overrides = json.loads(_call(system, user))
    except (AgentUnavailable, json.JSONDecodeError, TypeError):
        return {}
    valid = {"high", "medium", "low"}
    known_keys = {_key(p, t) for p, t in pending}
    return {k: v for k, v in overrides.items() if v in valid and k in known_keys}


# --- Act -----------------------------------------------------------------

def _with_overrides(pets: List[Pet], overrides: Dict[str, str]) -> List[Pet]:
    """Return copies of pets with suggested priorities applied; saved state is untouched."""
    if not overrides:
        return pets
    return [
        replace(
            pet,
            tasks=[
                replace(t, priority=Priority(overrides[_key(pet, t)]))
                if _key(pet, t) in overrides
                else t
                for t in pet.tasks
            ],
        )
        for pet in pets
    ]


# --- Check -----------------------------------------------------------------

def _starved_pets(pets: List[Pet], plan: List[Tuple[Pet, Task]]) -> List[Pet]:
    """Pets that had pending tasks but got nothing scheduled.

    Matched by name, not object identity: the plan is built from
    _with_overrides()'s copies of `pets`, so id() would never match.
    """
    scheduled_names = {p.name for p, _ in plan}
    return [p for p in pets if p.pending() and p.name not in scheduled_names]


def _map_to_originals(pets: List[Pet], plan: List[Tuple[Pet, Task]]) -> List[Tuple[Pet, Task]]:
    """Map a plan built from _with_overrides() copies back to the caller's
    original Pet/Task objects, so callers can use `id`/`in`/`is` against their
    own instances downstream (e.g. to compute skipped tasks or mark one done)
    without needing to know an override ever ran.
    """
    original_task_by_key = {(p.name, t.title): (p, t) for p in pets for t in p.tasks}
    return [original_task_by_key.get((p.name, t.title), (p, t)) for p, t in plan]


# --- Plan -> Act -> Check -> Revise loop ------------------------------------

def generate_plan(pets: List[Pet], owner: Owner) -> Tuple[List[Tuple[Pet, Task]], bool]:
    """Run the agentic scheduling loop.

    Falls back to the plain, unmodified scheduler (used_agent=False) if the
    agent is unavailable, never suggests a usable change, or every attempted
    override still starves a pet that used to get at least one task
    scheduled. Returns (plan, used_agent); plan pairs always reference the
    original pet/task objects passed in, never _with_overrides() copies.
    """
    overrides: Dict[str, str] = {}
    for _ in range(MAX_REVISE_ROUNDS):
        candidate = suggest_priority_overrides(_with_overrides(pets, overrides), owner)
        if not candidate:
            break
        trial_overrides = {**overrides, **candidate}
        plan = Scheduler.generate_owner_plan(_with_overrides(pets, trial_overrides), owner)
        # The scheduler itself already guarantees no overlaps/over-budget, so the
        # one failure mode left to catch here is the overrides starving a pet
        # that used to get at least one task scheduled.
        if not _starved_pets(pets, plan):
            return _map_to_originals(pets, plan), True
        overrides = trial_overrides  # keep refining and try again next round
    return Scheduler.generate_owner_plan(pets, owner), False


# --- Explain -----------------------------------------------------------------

def explain_plan(
    plan: List[Tuple[Pet, Task]],
    skipped: List[Tuple[Pet, Task]],
    owner: Owner,
) -> str:
    """Narrate a plan in plain language, grounded only in the tasks passed in.

    Raises AgentUnavailable (rather than returning a possibly-hallucinated
    answer) if the model's response doesn't reference any known task.
    """
    plan_listing = "\n".join(f"- {_describe(p, t)}" for p, t in plan) or "(none)"
    skipped_listing = "\n".join(f"- {_describe(p, t)}" for p, t in skipped) or "(none)"
    system = (
        "You explain a pet-care schedule to the owner in 3-5 warm, practical "
        "sentences. Only reference tasks listed below -- never invent a task, "
        "time, or pet that isn't present."
    )
    user = (
        f"Owner: {owner.name}, {owner.available_minutes} minutes available.\n\n"
        f"Scheduled:\n{plan_listing}\n\nSkipped:\n{skipped_listing}"
    )
    explanation = _call(system, user)
    known_titles = {t.title.lower() for _, t in [*plan, *skipped]}
    if known_titles and not any(title in explanation.lower() for title in known_titles):
        raise AgentUnavailable("Explanation did not reference any known task; discarded.")
    return explanation