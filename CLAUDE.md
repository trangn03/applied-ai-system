# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

PawPal+ — a Streamlit app that plans a pet owner's day by fitting care tasks into their available time,
with an optional Gemini-powered agent layered on top of a deterministic scheduler to nudge priorities
and narrate the plan in plain language.

## Commands

```bash
# Install deps (Python 3.13, project uses a `venv/` or `.venv/` virtualenv)
pip install -r requirements.txt

# Run the Streamlit UI
streamlit run app.py

# Run the CLI walkthrough (sorting/filtering/scheduling/conflicts/agent demo)
python main.py

# Run the full test suite
python -m pytest

# Run a single test file / test
python -m pytest test/test_pawpal.py
python -m pytest test/test_pawpal.py::test_find_conflicts_flags_overlapping_times -v

# AI reliability eval harness (consistency, plan validity, grounding)
python eval_agent.py
python eval_agent.py --runs 10
```

`GEMINI_API_KEY` must be set (env var or `.streamlit/secrets.toml`, which is gitignored) for the AI
layer to make real calls. Without it, the app and `eval_agent.py` both fall back gracefully
(the eval harness runs in a clearly-labelled **SIMULATED** mode).

## Architecture

Four layers, in order of dependency (full diagram: `diagrams/uml.mmd`):

1. **Data model** (`pawpal_system.py`): `Owner`, `Pet`, `Task` dataclasses and `Priority`/`Recurrence`
   enums. `Task.start_time` is an `"HH:MM"` string (matches the UI time picker), not minutes-from-midnight,
   so anything that orders tasks uses the `tuple(map(int, t.start_time.split(":")))` sort key rather than
   a plain string sort (un-padded hours like `"9:00"` sort wrong otherwise).

2. **Deterministic core** (`Scheduler` in `pawpal_system.py`): a greedy, priority-first planner
   (`fit_tasks_by_time`) that sorts pending tasks by priority and adds each one only if it still fits the
   owner's remaining time budget — it does not search for the time-optimal combination. This class is the
   **sole authority on correctness** (no double-booked tasks, never exceeding available time) and is
   unit-tested independently of both the UI and the AI layer. `find_conflicts` / `find_conflicts_among`
   detect per-pet and cross-pet (owner double-booked) overlaps, and correctly account for `due_date` so
   the same recurring time-of-day on different days isn't flagged.

3. **Agentic layer** (`agent.py`, sits on top of the scheduler, never replaces it): a
   Plan → Act → Check → Revise → Explain loop.
   - `suggest_priority_overrides` asks Gemini for priority overrides and filters the response to known
     task keys and valid `Priority` values only.
   - `generate_plan` applies overrides to in-memory task copies (`_with_overrides`, via
     `dataclasses.replace` — **never written back to the real task**), reruns the real `Scheduler`, and
     checks via `_starved_pets` whether any pet that used to get a scheduled task now gets none; it
     retries once before reverting to the un-overridden plan.
   - `explain_plan` narrates the result but is grounded: it raises `AgentUnavailable` unless the
     explanation mentions at least one real task title, to reject hallucinated summaries.
   - Every failure mode (no API key, network/API error, malformed JSON, ungrounded explanation) is caught
     and degrades to the plain scheduler's output (`used_agent=False`) or a caption — never an exception
     reaching the UI.

4. **UI / human-in-the-loop** (`app.py`): Streamlit front end — owner/pet/task entry, an AI-assistance
   toggle, and the review step where a human checks the AI's output (or the plain scheduler's) before
   acting on it. State is persisted as one JSON blob via `serialize_state`/`deserialize_state`
   (`pawpal_data.json`), not a database — every save rewrites the whole file.

**Reliability eval** (`eval_agent.py`, separate from `test/test_eval.py`'s unit tests on the metric
helpers themselves): since the agent is non-deterministic, this harness runs fixed scenarios N times and
reports (a) **consistency** — agreement rate of returned priority overrides across runs, (b)
**reliability** — every agent-produced plan is conflict-free and within budget (`plan_is_valid`), and (c)
**grounding** — how often `explain_plan`'s anti-hallucination check accepts the explanation.

## Design invariants to preserve when editing

- The AI layer may only *suggest priority overrides* and *narrate* — it must never choose tasks/times
  itself or bypass `Scheduler` for the actual plan.
- Priority overrides are per-run only; nothing from `agent.py` should mutate a stored `Task`.
- Any new AI failure mode must degrade to the deterministic scheduler's output, not raise into the UI.
- `test/test_pawpal.py` covers the deterministic core (sorting, filtering, conflicts, recurrence
  including month/year/leap-day boundaries, JSON round-trip); `test/test_agent.py` covers the agent's
  guardrails (override filtering, Plan→Act→Check→Revise, grounded explanations) by mocking `agent._call`
  directly so the suite runs deterministically offline; `test/test_eval.py` covers the eval harness's
  metric helpers. New tests should follow this split.
