# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.

## 🖥️ Sample Output

Paste a sample of your app's CLI or Streamlit output here so a reader can see what a generated plan looks like:

```
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
  09:05  [    ] Give medicine              20 min  [high]
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
===================================================================================================== test session starts =====================================================================================================
platform win32 -- Python 3.13.2, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\xtran\Downloads\ai110-module2show-pawpal-starter\.venv\Scripts\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\xtran\Downloads\ai110-module2show-pawpal-starter
plugins: anyio-4.14.0
collected 17 items                                                                                                                                                                                                             

test/test_pawpal.py::test_mark_complete_changes_status PASSED                                                                                                                                                            [  5%]
test/test_pawpal.py::test_add_task_increases_pet_task_count PASSED                                                                                                                                                       [ 11%]
test/test_pawpal.py::test_generate_plan_skips_conflicting_tasks PASSED                                                                                                                                                   [ 17%]
test/test_pawpal.py::test_generate_plan_keeps_non_overlapping_tasks PASSED                                                                                                                                               [ 23%]
test/test_pawpal.py::test_owner_plan_avoids_cross_pet_double_booking PASSED                                                                                                                                              [ 29%]
test/test_pawpal.py::test_owner_plan_shares_one_time_budget PASSED                                                                                                                                                       [ 35%]
test/test_pawpal.py::test_state_round_trips_through_serialization PASSED                                                                                                                                                 [ 41%]
test/test_pawpal.py::test_deserialize_handles_missing_owner PASSED                                                                                                                                                       [ 47%]
test/test_pawpal.py::test_sort_by_time_returns_chronological_order PASSED                                                                                                                                                [ 52%]
test/test_pawpal.py::test_sort_tasks_breaks_same_time_ties_by_priority_then_duration PASSED                                                                                                                              [ 58%]
test/test_pawpal.py::test_completing_daily_task_creates_next_day_occurrence PASSED                                                                                                                                       [ 64%]
test/test_pawpal.py::test_completing_weekly_task_advances_due_date_by_one_week PASSED                                                                                                                                    [ 70%]
test/test_pawpal.py::test_completing_non_recurring_task_creates_no_followup PASSED                                                                                                                                       [ 76%]
test/test_pawpal.py::test_find_conflicts_flags_overlapping_times PASSED                                                                                                                                                  [ 82%]
test/test_pawpal.py::test_find_conflicts_ignores_touching_but_non_overlapping_tasks PASSED                                                                                                                               [ 88%]
test/test_pawpal.py::test_completing_task_twice_does_not_double_queue PASSED                                                                                                                                             [ 94%]
test/test_pawpal.py::test_conflict_detection_respects_due_date_across_days PASSED                                                                                                                                        [100%]

===================================================================================================== 17 passed in 0.40s ======================================================================================================
```

## 📐 Smarter Scheduling

All scheduling logic lives in `pawpal_system.py` (the UI in `app.py` only calls into it), so every behavior below is unit-tested independently of Streamlit. The planner is a **priority-first greedy fit**: pending tasks are considered highest-priority first and a task is added to the plan only if it 
(a) fits the owner's remaining time budget and
(b) does not overlap a task already chosen — so the generated plan is always conflict-free,
not merely within budget.

| Feature | Method(s) | Notes |
|---------|-----------|-------|
| Task sorting | `Pet.sort_tasks`, `Scheduler.sort_by_time`, `Scheduler.sort_by_priority` | Multi-key sort: start time → priority → duration. Same-slot ties break toward higher priority, then the shorter task. |
| Filtering | `Pet.filter_tasks`, `Pet.pending`, `Scheduler.fit_tasks_by_time` | Filter by completion and/or priority; the planner skips tasks that don't fit the remaining time budget. |
| Conflict handling | `tasks_overlap`, `Scheduler.find_conflicts`, `Scheduler.find_conflicts_among` | Half-open overlap (touching ends don't conflict). Per-pet and cross-pet ("owner can't care for two pets at once") detection; the planner refuses to schedule overlapping tasks. |
| Multi-pet planning | `Scheduler.generate_owner_plan` | One shared time budget across all pets on a single timeline, so a high-priority task on one pet can bump a clashing task on another. |
| Recurring tasks | `Task.next_occurrence`, `Pet.complete_task` | Completing a `daily`/`weekly` task queues a fresh, pending copy with `due_date` advanced by one day or one week; non-recurring tasks queue nothing. |
| Persistence | `serialize_state`, `deserialize_state`, `Task/Pet/Owner.to_dict`/`from_dict` | Whole-app state round-trips through JSON so pets and tasks are stored when a browser refresh (and can be downloaded/restored as a backup). |

## 📸 Demo Walkthrough

Launch the app with `streamlit run app.py`, then follow along:

1. **List out the owner and pet.** Enter the owner's name and the minutes they have available today, then a pet's name and breed. Click **Save owner** and **Add / update pet** — both are confirmed back on screen. Add more pets the same way; one owner can manage several.
2. **Add tasks for a pet.** Pick a pet from the selector, then fill in a task (title, start time, duration, priority, and whether it repeats daily/weekly) and click **Add task**. Tasks are stored per pet and automatically sorted by start time.
3. **Track and filter tasks.** The task list shows each task's time, priority, and completion status. Use the **All / Pending / Completed** toggle to filter, and click **Done** to complete a task — recurring tasks automatically queue their next occurrence (e.g. a daily walk reappears for tomorrow).
4. **Spot conflicts.** If two of a pet's tasks overlap in time, a ⚠️ warning lists the clash. With multiple pets, cross-pet conflicts are flagged separately, since the owner can't care for two pets at once.
5. **Generate a schedule.** In **Generate Schedule**, choose **Selected pet** or **All pets (shared time)**, then click **Generate schedule**. The planner fits the highest-priority, non-overlapping tasks into the available time and lists what was scheduled, the total time used, and any skipped tasks — including a hint for how many more minutes would fit the ones left out.
6. **Keep your data.** Pets and tasks are saved automatically and stored when a browser refresh. Use the **💾 Data** sidebar to download a JSON backup or restore one.

**Screenshot or video** *(optional)*: <!-- Insert a screenshot or link to a demo video here -->
