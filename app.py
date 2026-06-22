import streamlit as st
from pawpal_system import Priority, Owner, Task, Pet, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.markdown("Plan your pet's day by adding tasks, then generate a schedule based on available time.")

st.divider()

# --- Owner & Pet ---
st.subheader("Owner & Pet")
col1, col2 = st.columns(2)
with col1:
    owner_name = st.text_input("Owner name", value="Jordan")
    available_minutes = st.number_input("Available time (minutes)", min_value=1, max_value=480, value=60)
with col2:
    pet_name = st.text_input("Pet name", value="Mochi")
    breed = st.text_input("Breed", value="Mixed")

if st.button("Save owner & pet"):
    st.session_state.owner = Owner(name=owner_name, available_minutes=int(available_minutes))
    st.session_state.pet = Pet(name=pet_name, breed=breed)

if "owner" in st.session_state and "pet" in st.session_state:
    st.success(f"Saved: {st.session_state.owner.name} caring for {st.session_state.pet.name}")

st.divider()

# --- Task list stored as Task objects in session state ---
if "tasks" not in st.session_state or (
    st.session_state.tasks and isinstance(st.session_state.tasks[0], dict)
):
    st.session_state.tasks = []

st.subheader("Tasks")
col1, col2, col3 = st.columns(3)
with col1:
    task_title = st.text_input("Task title", value="Morning walk")
with col2:
    duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
with col3:
    priority = st.selectbox("Priority", ["high", "medium", "low"])

if st.button("Add task"):
    st.session_state.tasks.append(
        Task(
            title=task_title,
            duration_minutes=int(duration),
            priority=Priority(priority),
        )
    )

if st.session_state.tasks:
    st.write("Current tasks:")
    st.table(
        [
            {
                "Title": t.title,
                "Duration (min)": t.duration_minutes,
                "Priority": t.priority.value,
                "Done": t.is_complete,
            }
            for t in st.session_state.tasks
        ]
    )
    if st.button("Clear all tasks"):
        st.session_state.tasks = []
        st.rerun()
else:
    st.info("No tasks yet. Add one above.")

st.divider()

# --- Schedule generation ---
st.subheader("Generate Schedule")

if st.button("Generate schedule"):
    if "owner" not in st.session_state:
        st.warning("Save your owner & pet info first.")
    elif not st.session_state.tasks:
        st.warning("Add at least one task before generating a schedule.")
    else:
        owner = st.session_state.owner
        pet = st.session_state.pet
        pet.tasks = list(st.session_state.tasks)
        scheduler = Scheduler(pet=pet, owner=owner)
        plan = scheduler.generate_plan()

        if not plan:
            st.warning("No tasks fit within the available time. Try adding shorter tasks or increasing available time.")
        else:
            st.success(f"Schedule for {pet.name} — {owner.name} has {owner.available_minutes} min available.")
            total = 0
            for i, task in enumerate(plan, start=1):
                total += task.duration_minutes
                st.markdown(
                    f"**{i}. {task.title}** — {task.duration_minutes} min "
                    f"(priority: {task.priority.value})"
                )
            st.info(f"Total time scheduled: {total} min out of {owner.available_minutes} min available.")

            skipped = [t for t in st.session_state.tasks if t not in plan and not t.is_complete]
            if skipped:
                st.markdown("**Skipped (did not fit):**")
                for t in skipped:
                    st.markdown(f"- {t.title} ({t.duration_minutes} min)")
