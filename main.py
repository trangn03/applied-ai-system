import os

from pawpal_system import Owner, Pet, Task, Scheduler, Priority, format_minutes
import agent
from agent import AgentUnavailable

# main.py has no Streamlit context, so fall back to reading the secrets file
# directly if GEMINI_API_KEY isn't already set in the environment.
if "GEMINI_API_KEY" not in os.environ:
    try:
        import tomllib

        with open(".streamlit/secrets.toml", "rb") as f:
            os.environ["GEMINI_API_KEY"] = tomllib.load(f)["GEMINI_API_KEY"]
    except (FileNotFoundError, KeyError, tomllib.TOMLDecodeError):
        pass

owner = Owner(name="Alex", available_minutes=120)

buddy = Pet(name="Buddy", breed="Golden Retriever")
whiskers = Pet(name="Whiskers", breed="Tabby Cat")

# Tasks are added OUT OF ORDER on purpose (note the start times) so we can
# see the sorting methods put them back in chronological order.
buddy.add_task(Task(title="Playtime in yard",   duration_minutes=25, priority=Priority.LOW,    start_time="17:00"))
buddy.add_task(Task(title="Morning walk",        duration_minutes=30, priority=Priority.HIGH,   start_time="07:30"))
buddy.add_task(Task(title="Brush coat",          duration_minutes=20, priority=Priority.MEDIUM, start_time="12:15"))
buddy.add_task(Task(title="Flea treatment",      duration_minutes=15, priority=Priority.HIGH,   start_time="9:00"))

whiskers.add_task(Task(title="Vet check-up",     duration_minutes=45, priority=Priority.MEDIUM, start_time="14:00"))
whiskers.add_task(Task(title="Litter box clean", duration_minutes=10, priority=Priority.HIGH,   start_time="08:00"))
whiskers.add_task(Task(title="Grooming session", duration_minutes=20, priority=Priority.LOW,    start_time="10:30"))

# Mark a couple of tasks complete so the completion filter has something to show.
buddy.tasks[1].mark_complete()       # Morning walk
whiskers.tasks[1].mark_complete()    # Litter box clean

# Deliberately overlapping tasks to exercise conflict detection:
#  - same pet: "Give medicine" 09:05-09:25 overlaps "Flea treatment" 09:00-09:15
buddy.add_task(Task(title="Give medicine", duration_minutes=20, priority=Priority.HIGH, start_time="09:05"))
#  - cross pet: Buddy "Evening feed" 14:10-14:30 overlaps Whiskers "Vet check-up" 14:00-14:45
buddy.add_task(Task(title="Evening feed", duration_minutes=20, priority=Priority.MEDIUM, start_time="14:10"))


def print_task(task: Task, pet_name: str | None = None) -> None:
    status = "[done]" if task.is_complete else "[    ]"
    title = f"{pet_name} - {task.title}" if pet_name else task.title
    width = 34 if pet_name else 25
    print(f"  {task.start_time:>5}  {status} {title:<{width}} {task.duration_minutes:>3} min  [{task.priority.value}]")


print("=" * 52)
print("        ADDED ORDER (as inserted)")
print("=" * 52)
for pet in [buddy, whiskers]:
    print(f"--- {pet.name} ({pet.breed}) ---")
    for task in pet.tasks:
        print_task(task)
    print()

print("=" * 52)
print("        SORTED BY START TIME")
print("=" * 52)
for pet in [buddy, whiskers]:
    scheduler = Scheduler(pet=pet, owner=owner)
    print(f"--- {pet.name} ({pet.breed}) ---")
    for task in scheduler.sort_by_time():
        print_task(task)
    print()

print("=" * 52)
print("        FILTERED: PENDING vs COMPLETED")
print("=" * 52)
for pet in [buddy, whiskers]:
    pet.sort_tasks()  # in-place sort by start time before filtering
    print(f"--- {pet.name} ({pet.breed}) ---")

    print("  Pending:")
    pending = pet.filter_tasks(complete=False)
    if pending:
        for task in pending:
            print_task(task)
    else:
        print("    (none)")

    print("  Completed:")
    completed = pet.filter_tasks(complete=True)
    if completed:
        for task in completed:
            print_task(task)
    else:
        print("    (none)")
    print()

print("=" * 52)
print("        TODAY'S SCHEDULE (fits available time)")
print("=" * 52)
print(f"Owner : {owner.name}  |  Available: {owner.available_minutes} min\n")
for pet in [buddy, whiskers]:
    scheduler = Scheduler(pet=pet, owner=owner)
    plan = scheduler.generate_plan()

    print(f"--- {pet.name} ({pet.breed}) ---")
    if plan:
        for task in plan:
            print_task(task)
    else:
        print("  No tasks fit within the available time.")
    print()


def span(task: Task) -> str:
    return f"{task.start_time}-{format_minutes(task.end_minutes)}"


print("=" * 52)
print("        CONFLICT DETECTION")
print("=" * 52)

# Per-pet conflicts.
for pet in [buddy, whiskers]:
    scheduler = Scheduler(pet=pet, owner=owner)
    conflicts = scheduler.find_conflicts()
    print(f"--- {pet.name} ---")
    if conflicts:
        for a, b in conflicts:
            print(f"  [CONFLICT] '{a.title}' ({span(a)}) overlaps '{b.title}' ({span(b)})")
    else:
        print("  No conflicts.")
    print()

# Owner-wide conflicts across different pets (can't care for two at once).
print("--- Across pets (owner double-booked) ---")
cross = [
    (pa, ta, pb, tb)
    for pa, ta, pb, tb in Scheduler.find_conflicts_among([buddy, whiskers])
    if pa is not pb
]
if cross:
    for pa, ta, pb, tb in cross:
        print(f"  [CONFLICT] {pa.name}'s '{ta.title}' ({span(ta)}) overlaps {pb.name}'s '{tb.title}' ({span(tb)})")
else:
    print("  No cross-pet conflicts.")

print("\n" + "=" * 52)

print("=" * 52)
print("        AI-ASSISTED PLANNING (agent.py)")
print("=" * 52)

pets = [buddy, whiskers]
plan, used_agent = agent.generate_plan(pets, owner)

print(f"Owner : {owner.name}  |  Available: {owner.available_minutes} min")
print(f"Agent adjusted priorities for this run: {used_agent}\n")

if plan:
    for pet, task in plan:
        print_task(task, pet_name=pet.name)
else:
    print("  No tasks fit within the available time.")

chosen = {id(task) for _, task in plan}
skipped = [(pet, t) for pet in pets for t in pet.pending() if id(t) not in chosen]
if skipped:
    print("\nSkipped:")
    for pet, task in skipped:
        print_task(task, pet_name=pet.name)

print()
try:
    print("AI summary:", agent.explain_plan(plan, skipped, owner))
except AgentUnavailable as exc:
    print(f"AI summary unavailable ({exc}) -- the plan above still came from "
          "the plain, deterministic scheduler regardless.")

print("\n" + "=" * 52)
