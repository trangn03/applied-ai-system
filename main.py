from pawpal_system import Owner, Pet, Task, Scheduler, Priority

owner = Owner(name="Alex", available_minutes=120)

buddy = Pet(name="Buddy", breed="Golden Retriever")
whiskers = Pet(name="Whiskers", breed="Tabby Cat")

buddy.add_task(Task(title="Morning walk",       duration_minutes=30, priority=Priority.HIGH))
buddy.add_task(Task(title="Flea treatment",     duration_minutes=15, priority=Priority.HIGH))
buddy.add_task(Task(title="Brush coat",         duration_minutes=20, priority=Priority.MEDIUM))
buddy.add_task(Task(title="Playtime in yard",   duration_minutes=25, priority=Priority.LOW))

whiskers.add_task(Task(title="Litter box clean", duration_minutes=10, priority=Priority.HIGH))
whiskers.add_task(Task(title="Vet check-up",     duration_minutes=45, priority=Priority.MEDIUM))
whiskers.add_task(Task(title="Grooming session", duration_minutes=20, priority=Priority.LOW))

print("=" * 40)
print("        TODAY'S SCHEDULE")
print("=" * 40)
print(f"Owner : {owner.name}  |  Available: {owner.available_minutes} min\n")

for pet in [buddy, whiskers]:
    scheduler = Scheduler(pet=pet, owner=owner)
    plan = scheduler.generate_plan()

    print(f"--- {pet.name} ({pet.breed}) ---")
    if plan:
        for task in plan:
            status = "[done]" if task.is_complete else "[    ]"
            print(f"  {status} {task.title:<25} {task.duration_minutes:>3} min  [{task.priority.value}]")
    else:
        print("  No tasks fit within the available time.")
    print()

print("=" * 40)
