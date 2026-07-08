# PawPal+ 

**PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.


## Original Project (Modules 2): PawPal+

This project builds on **PawPal+**, my original Modules 2 project. PawPal+'s original goal was a Streamlit app that lets a pet owner enter owner/pet info, add and manage care tasks (walks, feeding, meds, grooming) with a duration and priority, and generate a conflict-free daily schedule that fits within the owner's available time. It included a deterministic, priority-first greedy scheduler (`pawpal_system.py`) with a unit-test suite covering sorting, conflict detection, and recurring tasks, connected to a Streamlit UI (`app.py`).

## What previously build
- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## What is added for the project

**PawPal+: an AI-assisted pet-care scheduler.** 
It plans a pet owner's day by fitting care tasks into their available time without conflicts, and now optionally layers a Gemini-powered agent on top of the original deterministic scheduler to fine-tune task priorities and explain the resulting plan in plain language. It matters because a busy owner juggling multiple pets needs a plan that is both provably correct (no double-booked tasks, never exceeding available time) and easy to trust — the AI layer can only nudge priorities and narrate, never override the scheduler's guarantees, so the app stays reliable even if the AI is unavailable or wrong.

## Architecture Overview

The full system diagram is in [`diagrams/uml.mmd`](diagrams/uml.mmd) (a Mermaid flowchart). It shows four layers:

- **Data model** (`pawpal_system.py`): `Owner`, `Pet`, and `Task` dataclasses, plus `Priority`/`Recurrence` enums — the original Modules 1–3 classes.
- **Deterministic core** (`Scheduler`): a greedy, priority-first planner that sorts pending tasks by priority, then fits them into the owner's time budget while rejecting overlaps. This remains the sole authority on correctness and is unit-tested independently of the UI.
- **Agentic layer** (`agent.py`, added on top of the original project): an optional Plan → Act → Check → Revise → Explain loop — it asks Gemini to suggest priority overrides, reruns the real `Scheduler` with them, checks the result didn't starve a pet of every task, retries once if it did, and finally narrates the plan. Any failure (no API key, bad response, ungrounded explanation) falls back to the plain scheduler output.
- **UI and human-in-the-loop** (`app.py`): a Streamlit front end where the owner enters data, toggles AI assistance on/off, and reviews, edits, or marks tasks done — the point where a human checks the AI's output before it becomes the plan they act on.



## Setup Instructions

### Step 1: Clone the repository

```bash
git clone <this-repo-url>
cd applied-ai-system
```

### Step 2: Create and activate the virtual environment

```bash
python -m venv .venv
source .venv/bin/activate  # MacOS & Linux
.venv\Scripts\activate     # Windows
```

### Step 3: Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure the AI agent

The "Use AI" checkbox in the app needs a Gemini API key. Without one, the app still works — it just falls back to the plain deterministic scheduler.

Set it as an environment variable:

```bash
export GEMINI_API_KEY="your-key-here"   # MacOS & Linux
$env:GEMINI_API_KEY = "your-key-here"   # Windows PowerShell
```

or add it to `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your-key-here"
```

`.streamlit/secrets.toml` is gitignored — never commit a real key to the repo.

### Step 5: Run the app

```bash
streamlit run app.py
```

This opens PawPal+ in your browser (default: `http://localhost:8501`).

### Step 6: Run the tests

```bash
python -m pytest
```

## Suggested workflow (for extending the project)

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## Sample Interactions

Three examples of the AI agent's input → output behavior (see `agent.py` and `test/test_agent.py`).

### 1. Priority override + explanation

Input — Buddy has a `medium`-priority "Vet visit" (30 min, 09:00) and a `medium`-priority "Grooming" (30 min, 09:00) that overlap; owner has 30 min available and checks "Use AI".

AI output:

```text
🤖 One or more priorities were adjusted by the AI planner for this run.

1. 09:00 · Buddy — Vet visit — 30 min (priority: high)

🤖 AI summary: I've bumped Buddy's vet visit to the top of today's list since
it's a health task that shouldn't slip — grooming can wait for another day
when there's more time to spare.
```

The agent judged "Vet visit" as under-prioritized relative to "Grooming", bumped it to `high` for this run only (nothing is saved back to the task), reran the real `Scheduler`, and confirmed the winner still got scheduled before explaining the result.

### 2. No override needed → falls back to the plain scheduler

Input — a single well-prioritized task, e.g. Buddy's "Walk" (`high`, 20 min, 09:00), owner has 60 min available.

AI output:

```text
1. Walk — 20 min (priority: high)

🤖 AI summary: Buddy's walk is all set for 9:00 this morning — a great way to
start the day, and there's plenty of time left over if you'd like to add
another task.
```

No "priorities were adjusted" caption appears, since `suggest_priority_overrides` returned no changes — the schedule is the same one `Scheduler.generate_owner_plan` would have produced without AI, and only the narration step ran.

### 3. AI unavailable → graceful degradation

Input — same as example 2, but `GEMINI_API_KEY` isn't set (or the Gemini API call fails/returns an ungrounded response).

AI output:

```text
1. Walk — 20 min (priority: high)

AI explanation unavailable (GEMINI_API_KEY is not set.).
```

`generate_plan` catches the failure and returns the plain scheduler's plan (`used_agent=False`); `explain_plan` raises `AgentUnavailable`, which `app.py` catches and shows as a caption instead of crashing the page.


## 🖥️ Sample Output

Sample of app's CLI or Streamlit output:

```
..........................                  
====================================================
        ADDED ORDER (as inserted)
====================================================
--- Buddy (Golden Retriever) ---
  17:00  [    ] Playtime in yard           25 min  [low]
  07:30  [done] Morning walk               30 min  [high]
  12:15  [    ] Brush coat                 20 min  [medium]
   9:00  [    ] Flea treatment             15 min  [high]
  09:05  [    ] Give medicine              20 min  [high]
  14:10  [    ] Evening feed               20 min  [medium]

--- Whiskers (Tabby Cat) ---
  14:00  [    ] Vet check-up               45 min  [medium]
  08:00  [done] Litter box clean           10 min  [high]
  10:30  [    ] Grooming session           20 min  [low]

====================================================
        SORTED BY START TIME
====================================================
--- Buddy (Golden Retriever) ---
  07:30  [done] Morning walk               30 min  [high]
   9:00  [    ] Flea treatment             15 min  [high]
  09:05  [    ] Give medicine              20 min  [high]
  12:15  [    ] Brush coat                 20 min  [medium]
  14:10  [    ] Evening feed               20 min  [medium]
  17:00  [    ] Playtime in yard           25 min  [low]

--- Whiskers (Tabby Cat) ---
  08:00  [done] Litter box clean           10 min  [high]
  10:30  [    ] Grooming session           20 min  [low]
  14:00  [    ] Vet check-up               45 min  [medium]

====================================================
        FILTERED: PENDING vs COMPLETED
====================================================
--- Buddy (Golden Retriever) ---
  Pending:
   9:00  [    ] Flea treatment             15 min  [high]
  09:05  [    ] Give medicine              20 min  [high]
  12:15  [    ] Brush coat                 20 min  [medium]
  14:10  [    ] Evening feed               20 min  [medium]
  17:00  [    ] Playtime in yard           25 min  [low]
  Completed:
  07:30  [done] Morning walk               30 min  [high]

--- Whiskers (Tabby Cat) ---
  Pending:
  10:30  [    ] Grooming session           20 min  [low]
  14:00  [    ] Vet check-up               45 min  [medium]
  Completed:
  08:00  [done] Litter box clean           10 min  [high]

====================================================
        TODAY'S SCHEDULE (fits available time)
====================================================
Owner : Alex  |  Available: 120 min

--- Buddy (Golden Retriever) ---
   9:00  [    ] Flea treatment             15 min  [high]
  12:15  [    ] Brush coat                 20 min  [medium]
  14:10  [    ] Evening feed               20 min  [medium]
  17:00  [    ] Playtime in yard           25 min  [low]

--- Whiskers (Tabby Cat) ---
  14:00  [    ] Vet check-up               45 min  [medium]
  10:30  [    ] Grooming session           20 min  [low]

====================================================
        CONFLICT DETECTION
====================================================
--- Buddy ---
  [CONFLICT] 'Flea treatment' (9:00-09:15) overlaps 'Give medicine' (09:05-09:25)

--- Whiskers ---
  No conflicts.

--- Across pets (owner double-booked) ---
  [CONFLICT] Whiskers's 'Vet check-up' (14:00-14:45) overlaps Buddy's 'Evening feed' (14:10-14:30)

====================================================
====================================================
        AI-ASSISTED PLANNING (agent.py)
====================================================
Owner : Alex  |  Available: 120 min
Agent adjusted priorities for this run: True

   9:00  [    ] Buddy - Flea treatment     15 min  [high]
  10:30  [    ] Whiskers - Grooming session  20 min  [low]
  12:15  [    ] Buddy - Brush coat         20 min  [medium]
  14:00  [    ] Whiskers - Vet check-up    45 min  [medium]

Skipped:
  09:05  [    ] Buddy - Give medicine      20 min  [high]
  14:10  [    ] Buddy - Evening feed       20 min  [medium]
  17:00  [    ] Buddy - Playtime in yard   25 min  [low]

AI summary: I've mapped out a great schedule for your pets today, Alex! Buddy will receive his flea treatment first thing, followed by a good brush later on. Whiskers is scheduled for a relaxing grooming session before her vet check-up. We'll need to skip Buddy's medicine, evening feed, and playtime today.

====================================================
```

## 🧪 Testing PawPal+

```bash
# Run the full test suite:
python -m pytest

# Individual test names:
python -m pytest -v

# Run with coverage:
pytest --cov
```

Sample test output:

```
======================================= test session starts =======================================
platform win32 -- Python 3.14.4, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\...\applied-ai-system
plugins: anyio-4.14.1
collected 45 items

test/test_agent.py ........                                                                 [ 20%]
test/test_eval.py .........                                                                 [ 40%]
test/test_pawpal.py ............................                                            [100%]

======================================= 45 passed in 0.23s ========================================
```

The suite spans three files:

- `test/test_pawpal.py` — the deterministic core, including edge cases for input validation, recurrence across month/year/leap-day boundaries, overdue-task catch-up, and the midnight time-of-day boundary.
- `test/test_agent.py` — the agentic layer's guardrails (override filtering, Plan→Act→Check→Revise, grounded explanations).
- `test/test_eval.py` — the reliability-eval metric helpers and the invariant that every agent-produced plan is valid.

## Testing Summary

**What worked.** All 45 tests pass, split across `test/test_pawpal.py` (the deterministic core: sorting, filtering, conflict detection, recurrence, multi-pet/shared-budget planning, and JSON serialization round-trips) and `test/test_agent.py` (the agentic layer: overrides are filtered to known tasks/valid priorities, the Plan→Act→Check→Revise loop applies a valid override but reverts cleanly when an override can't avoid starving a pet, and `explain_plan` accepts grounded text but rejects a hallucinated one). Every agent test mocks `agent._call` directly, so the suite runs deterministically offline with no real Gemini API calls or key required.

**What didn't work at first.** Writing the edge-case tests surfaced two real bugs before they could reach a user: `complete_task` had no guard against being called twice, so completing an already-done task silently queued a duplicate future occurrence; and `find_conflicts` compared only time-of-day and ignored `due_date`, so a recurring 09:00 walk on Monday was falsely flagged as conflicting with the same walk on Tuesday. Both were fixed and locked in by `test_completing_task_twice_does_not_double_queue` and `test_conflict_detection_respects_due_date_across_days`.

**What I learned.** Tests catch bugs that manual clicking through the UI doesn't — both bugs above only showed up once an edge case was written down and asserted on. The other lesson is scope: the deterministic core has full unit coverage, but the AI layer's *quality* (is a suggested override actually a good idea, is an explanation well-written) isn't something a test suite can grade — that's why `agent.py` leans on runtime guardrails (the Check/Revise starvation check, the grounding check in `explain_plan`) and human review in the UI, rather than tests, to catch bad AI output.

**What I tested next (now covered).** The edge cases previously listed as untested are now in `test/test_pawpal.py`: zero/negative duration and negative `available_minutes` (rejected at construction via `__post_init__`), recurrence stepping across a month, year, and leap-day boundary, the midnight time-of-day boundary (`end_minutes` runs past 1440 while display wraps), and completing a long-overdue daily task (its next occurrence now *catches up* to the reference day instead of requeuing in the past). Writing these surfaced and fixed the input-validation gap and the overdue-recurrence behavior.

## 🔬 AI Reliability Eval (`eval_agent.py`)

Because the agent is non-deterministic, unit tests can pin down its *guardrails* but not its *behavior over repeated runs*. `eval_agent.py` is a small harness that measures exactly that — it satisfies the "Reliability or Testing System" AI feature (*"a script that checks if your AI gives consistent answers"*):

```bash
python eval_agent.py            # uses live Gemini if GEMINI_API_KEY is set
python eval_agent.py --runs 10  # more samples per scenario
```

For each fixed scenario it reports three things:

- **Consistency** — runs the same request N times and reports how often the agent returns the *same* priority overrides (an agreement rate + per-key stability). A scheduler an owner trusts shouldn't give a wildly different answer every run.
- **Reliability** — confirms the core invariant holds on every run: no matter what the LLM suggested, the plan the agent returns is **conflict-free and within budget** (`plan_is_valid`). This is the promise the whole "AI advises, scheduler decides" design makes.
- **Grounding** — runs `explain_plan` N times and counts how often the anti-hallucination check accepts the explanation.

Without a `GEMINI_API_KEY` it runs in a clearly-labelled **SIMULATED** mode (canned answers, no API calls) so the report format is demonstrable offline. The metric helpers (`consistency_report`, `plan_is_valid`) are themselves unit-tested in `test/test_eval.py`.

## Design Decisions

Key choices behind PawPal+, and the trade-off each one makes.

- **Greedy, priority-first scheduling instead of an optimal packer.** `fit_tasks_by_time` sorts pending tasks by priority and adds each one only if it still fits the remaining time budget — it doesn't search for the time-optimal combination. Trade-off: with 60 minutes available and tasks of 50 (high), 30 (medium), and 30 (medium) minutes, it picks the 50-minute task and leaves 10 minutes unused, even though the two 30-minute tasks together would fill the hour. This is reasonable for pet care, since an owner cares more about the important task happening at all than about squeezing every spare minute out of the day.

- **The AI layer can only nudge priorities and narrate — it never picks tasks or times itself.** `Scheduler.generate_owner_plan` stays the sole authority on correctness (time budget, no overlaps); `agent.py` only proposes priority overrides, which are validated by rerunning the real scheduler. Trade-off: this caps how much the AI can improve a schedule (it can't invent a smarter packing than the greedy algorithm allows), but it guarantees the app can never produce an invalid schedule because of a bad LLM response.

- **Priority overrides are never saved back to a task.** `_with_overrides` applies suggestions to in-memory copies (`dataclasses.replace`) only, so an AI suggestion affects just the current "Generate schedule" click. Trade-off: the owner doesn't get a persistent priority correction, but a single bad LLM call can never quietly corrupt their saved data.

- **A Check/Revise loop instead of trusting the LLM's first answer.** After applying overrides, `generate_plan` checks whether any pet that used to get a scheduled task now gets none (`_starved_pets`), and retries up to twice before giving up. Trade-off: up to two extra API calls per schedule generation, in exchange for catching the AI over-correcting one pet's priorities at another pet's expense.

- **`explain_plan` is grounded and fails closed.** The generated explanation is rejected (raises `AgentUnavailable`) unless it mentions at least one real task title, to catch hallucinated summaries. Trade-off: an unlucky paraphrase (e.g. "morning stroll" instead of "Walk") could be falsely rejected, but silently showing the owner an invented explanation is worse.

- **Every AI failure degrades to the plain scheduler, never a crash.** A missing API key, network error, malformed JSON, and an ungrounded explanation are all caught and mapped to `used_agent=False` or a caption, instead of an exception reaching the UI. Trade-off: the owner doesn't always learn *why* the AI step was skipped, but the app stays fully usable with zero AI configuration.

- **Task start time is an `"HH:MM"` string, not minutes-from-midnight.** This matches what the UI's time picker and task list actually display. Trade-off: sorting needs a small parsing key (`tuple(map(int, t.start_time.split(":")))`) everywhere tasks are ordered, since a plain string sort breaks on un-padded hours like `"9:00"`.

- **Whole-app state is one JSON file, not a database.** `serialize_state`/`deserialize_state` round-trip everything through a single `pawpal_data.json` on every save, which keeps backup/restore a one-click download/upload. Trade-off: every save rewrites the whole file, and there's no way to query tasks by date or status without loading everything into memory — a real database (e.g. SQLite) would scale better as task history grows.

## 📸 Demo Walkthrough

Launch the app with `streamlit run app.py`, then follow along:

1. **List out the owner and pet.** Enter the owner's name and the minutes they have available today, then a pet's name and breed. Click **Save owner** and **Add / update pet** — both are confirmed back on screen. Add more pets the same way; one owner can manage several.
2. **Add tasks for a pet.** Pick a pet from the selector, then fill in a task (title, start time, duration, priority, and whether it repeats daily/weekly) and click **Add task**. Tasks are stored per pet and automatically sorted by start time.
3. **Track and filter tasks.** The task list shows each task's time, priority, and completion status. Use the **All / Pending / Completed** toggle to filter, and click **Done** to complete a task — recurring tasks automatically queue their next occurrence (e.g. a daily walk reappears for tomorrow).
4. **Spot conflicts.** If two of a pet's tasks overlap in time, a ⚠️ warning lists the clash. With multiple pets, cross-pet conflicts are flagged separately, since the owner can't care for two pets at once.
5. **Generate a schedule.** In **Generate Schedule**, choose **Selected pet** or **All pets (shared time)**, then click **Generate schedule**. The planner fits the highest-priority, non-overlapping tasks into the available time and lists what was scheduled, the total time used, and any skipped tasks — including a hint for how many more minutes would fit the ones left out.
6. **Keep your data.** Pets and tasks are saved automatically and stored when a browser refresh. Use the **💾 Data** sidebar to download a JSON backup or restore one.

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->

## Reflection

Working with AI on both the original scheduler and the new AI layer taught me to treat it as a helper, not a source of final answers — its work still needs a human (or a test suite) to check it. The best way to work with it was one small feature at a time: ask for one thing ("start with sorting by time," then "move on to filtering"), test that it works with `pytest`, then move to the next thing. I stayed in charge of *what* to build and *why*; the AI mostly helped with *how*.

**A helpful suggestion.** I needed a way to detect when two tasks' times overlap. The AI suggested sorting tasks by start time first, then comparing each task only to the ones after it, stopping early once a later task starts after the current one ends (`Scheduler.find_conflicts`). This is much faster than comparing every task to every other task, and I could quickly confirm it worked by running the existing tests.

**A flawed suggestion.** When adding a start time to each task, the AI's first implementation stored it as an integer (minutes from midnight) and recommended keeping it that way for simplicity. I didn't accept it as-is, since that didn't match what the time picker and task list actually display as `"HH:MM"`. Switching to a string surfaced a bug the AI hadn't flagged on its own: a plain string sort breaks on un-padded hours like `"9:00"` (it would sort after `"09:05"` but before `"12:15"` incorrectly). The fix was a small parsing key, `tuple(map(int, t.start_time.split(":")))`, which I verified by feeding the scheduler out-of-order and un-padded times and checking the printed order was still correct.

**Takeaway.** AI is great at speeding up the exploring and the repetitive parts of coding. But the judgment calls — does this data type actually match what the UI needs, is this edge case handled, does this "explanation" actually match the real data — still have to come from me. I only catch those by trying to break the AI's suggestion myself, not by trusting it the first time.
