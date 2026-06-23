# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
  - Enter owner and pet info which includes pet name, breed, available time per day that the scheduler will be use as constrain
  - Add and manage care tasks which includes create, edit, remove tasks such as feeding, walks, medications, or grooming. Each will have a duration and priority level
  - Generate and view daily plan will use the scheduler to list out the daily schedule for a pet based on entered tasks and constrains.
- What classes did you include, and what responsibilities did you assign to each?
  - There are four classes that I include
    - ```Owner```: pet's owner name, time availability and their request service 
    - ```Pet```: holds pet info, list of task, manages adding, removing, and sorting
    - ```Task```: represents the care activities (name, duration, priority), completion status
    - ```Scheduler```: builds daily schedule based on pet's plan, sort by priority, fit tasks into available time, and delegates task completion
  - I also added two supporting enumerations, ```Priority``` (high/medium/low) and ```Recurrence``` (none/daily/weekly), which the ```Task``` class uses.

**b. Design changes**

- Did your design change during implementation?
- If yes, describe at least one change and why you made it.
  - Yes, I added an enumeration class called ```Priority``` for the scheduler which determine what task should complete first. There are three level apply called high, medium, and low. 

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- What constraints does your scheduler consider (for example: time, priority, preferences)?
  - The scheduler contains 
    - Time which includes if its ```duration_minutes``` fits within the owner's remaining ```available_minutes```
    - Priority as tasks are sorted from high to low before the time check, so higher priority tasks get first access to the available time. 
- How did you decide which constraints mattered most?
  - I decide which constraints mattered the most by focusing on the pet condition. Based on that, I will able to set priority with the pet. For instance medication would be set higher than grooming. Additionally, time availability is also an important factor as if a task doesn't fit in the owner's available time, it simply can not happen that day.

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
  - My scheduler uses a greedy, priority-first approach. In ```fit_tasks_by_time``` I sort the pending tasks from high to low priority and then add each one only if it still fits in the remaining time. The implementation will choose the most important tasks, but can waste time or skip a better combination. For example, with 60 minutes available and tasks of 50 (high), 30 (medium), and 30 (medium) minutes, my scheduler picks the 50-minute high-priority task and leaves 10 minutes unused, even though the two 30-minute tasks together would have filled the whole hour. A true optimization (0/1 knapsack) would compare every combination, but I chose not to do that.
- Why is that tradeoff reasonable for this scenario?
  - This is a reasonable tradeoff because a pet owner cares more about *the important tasks getting done* than about squeezing every last minute out of the day. Medication and feeding should win the time slot over playtime, and greedy-by-priority guarantees that. 

---

## 3. AI Collaboration

**a. How you used AI**

- How did you use AI tools during this project (for example: design brainstorming, debugging, refactoring)?
  - I used Claude AI across different phases for the project
    - Design brainstorming: I asked Claude for a list of small algorithm and logic improvements to make the scheduler more efficient (sorting by time, filtering by pet/status, recurring tasks, and conflict detection). It suggested concrete approaches like adding a start-time field, a single multi-key sort, and an interval-overlap check, which gave me a clear roadmap of features to build.
    - Debugging/Refactoring: Claude helped me refactor duplicated logic, such as pulling the "skip completed tasks" check into a reusable ```pending()``` method and routing task completion through one place. It also caught a Windows terminal crash where the ⚠️ emoji could not be encoded in cp1252, and fixed it by using a plain ```[CONFLICT]``` label for terminal output while keeping the emoji in the Streamlit UI.
    - Documentation: I used Claude to write clear docstrings and comments explaining *why* the code works.
    - UI enhancement: Claude helped me extend the Streamlit app with a start-time picker, a "show All/Pending/Completed" status filter, multi-pet support with a pet selector, a "Repeats" dropdown for recurring tasks, and warning messages for scheduling conflicts.
    - Testing: Claude verified each feature in the terminal by adding out-of-order and deliberately overlapping tasks to ```main.py```, running it, and checking the printed output. It also ran the existing pytest suite after every change to make sure nothing broke.
- What kinds of prompts or questions were most helpful?
  - The most helpful prompts were asking for *one feature at a time* ("start with sorting by time," then "move on to filtering") instead of everything at once, which kept each change small and easy to review. Conceptual "how does this work" questions (like how to use a lambda as a sort key for "HH:MM" strings) were also useful because they helped me understand the code rather than just copy it, so I could decide between storing the time as an integer or a string myself.

**b. Judgment and verification**

- Describe one moment where you did not accept an AI suggestion as-is.
  - When I added a start time to each task, Claude implemented it by storing the time as an integer (minutes from midnight) and recommended keeping it that way because it would be more simple. I did not accept that as-is. I asked it to switch the model to a ```"HH:MM"``` string instead, since that is what the time picker and the task list actually display, and it felt more natural to read and store. Claude pointed out the tradeoff — that a plain string sort breaks on un-padded hours like ```"9:00"``` — so we kept the string field but used a lambda key, ```tuple(map(int, t.start_time.split(":")))```, that parses it into ```(hour, minute)``` so the sort stays correct.
- How did you evaluate or verify what the AI suggested?
  - I verified the change by running ```main.py``` with tasks added out of order, including a deliberately un-padded ```"9:00"``` time, and checking that the printed schedule still came out in the right order (```07:30, 9:00, 12:15, 17:00```). I also ran the existing ```pytest``` suite after the change to confirm nothing else broke. Asking the conceptual lambda question first helped me understand *why* the string approach needed special handling

---

## 4. Testing and Verification

**a. What you tested**

- What behaviors did you test?
  - I tested the three core behaviors of the scheduler, plus two edge cases that Claude suggest:
    - **Sorting correctness** — that ```sort_by_time``` returns tasks in chronological order regardless of the order they were added, and that same-time ties break by priority then duration.
    - **Recurrence logic** — that completing a daily task marks it done and queues a fresh, incomplete copy due the next day, that a weekly task advances by seven days, and that a non-recurring task creates no follow-up.
    - **Conflict detection** — that the ```Scheduler``` flags two tasks sharing the same time slot as a conflict, and that two tasks merely touching end-to-end (e.g. 09:00–09:30 and 09:30 onward) are not flagged.
    - **Two edge cases** — completing an already-complete task should not queue a duplicate occurrence, and two recurring occurrences at the same time but on different days should not count as a conflict.
- Why were these tests important?
  - These tests cover the three features that — ordering, recurrence, and conflict detection — so a regression in any of them would directly produce a wrong daily plan for the owner. They were especially important because the edge-case tests caught two bugs I would not have noticed by manual testing: ```complete_task``` had no guard against being called twice, so it silently created duplicate future tasks, and ```find_conflicts``` compared only the time of day and ignored ```due_date```, so it falsely flagged a recurring 09:00 walk on Monday as conflicting with the same walk on Tuesday. 

**b. Confidence**

- How confident are you that your scheduler works correctly?
  - I am fairly confident in the core behavior. The full pytest suite (17 tests) passes, and it covers sorting, recurrence, conflict detection, the greedy time-fitting plan, multi-pet scheduling against a shared time budget, and state serialization round-trips. Writing tests also forced bugs to the surface and confirmed the fixes, which raised my confidence beyond just "it looked right when I ran it." 
- What edge cases would you test next if you had more time?
  - **Tasks crossing midnight** — a 23:00 task lasting two hours, since ```end_minutes``` can exceed 1440 and never wraps, so a late-night task may not overlap-check correctly against an early-morning one.
  - **Zero or negative duration**, and an ```available_minutes``` of 0 or negative, to confirm the planner degrades gracefully.
  - **Recurrence boundaries** — a weekly task crossing a month/year end, and a daily task across the leap day, to confirm date stepping stays correct.
  - **Overdue catch-up** — completing a daily task whose ```due_date``` is several days in the past, to decide whether the next occurrence should still land one day later or catch up to today.

---

## 5. Reflection

**a. What went well**

- What part of this project are you most satisfied with?

**b. What you would improve**

- If you had another iteration, what would you improve or redesign?

**c. Key takeaway**

- What is one important thing you learned about designing systems or working with AI on this project?
