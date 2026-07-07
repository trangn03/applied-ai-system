import json
import os
from datetime import time
from pathlib import Path

import streamlit as st
from pawpal_system import (
    Priority,
    Recurrence,
    Owner,
    Task,
    Pet,
    Scheduler,
    format_minutes,
    tasks_overlap,
    serialize_state,
    deserialize_state,
)
import agent
from agent import AgentUnavailable

# State is mirrored to this file so a browser refresh doesn't wipe the day.
DATA_FILE = Path(__file__).parent / "pawpal_data.json"

# Let the API key come from Streamlit secrets (e.g. on Streamlit Cloud) if it
# isn't already in the environment; agent.py itself only looks at the env var.
if "GEMINI_API_KEY" not in os.environ:
    try:
        os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass


def t_end(task: Task) -> str:
    """End time of a task as an HH:MM string."""
    return format_minutes(task.end_minutes)


def render_overflow_hint(skipped: list[Task], plan: list[Task]) -> None:
    """Tell the user how much extra time would fit the time-skipped tasks.

    Tasks skipped only because the budget ran out can be fixed by adding
    minutes; tasks skipped because they overlap a scheduled task cannot — they
    need rescheduling. The two are reported separately so the advice is honest.
    """
    time_skipped = [t for t in skipped if not any(tasks_overlap(t, p) for p in plan)]
    conflict_skipped = [t for t in skipped if any(tasks_overlap(t, p) for p in plan)]
    if time_skipped:
        extra = sum(t.duration_minutes for t in time_skipped)
        st.info(
            f"⏱️ Add about **{extra} more minute(s)** to fit the "
            f"{len(time_skipped)} task(s) skipped for time."
        )
    if conflict_skipped:
        st.caption(
            f"🔀 {len(conflict_skipped)} task(s) were skipped due to time "
            "conflicts — adding minutes won't help; reschedule them instead."
        )


def load_state() -> None:
    """Populate session_state from the data file, if it exists and is valid."""
    if not DATA_FILE.exists():
        return
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        owner, pets = deserialize_state(data)
    except (json.JSONDecodeError, KeyError, ValueError):
        return  # corrupt/old file: start fresh rather than crash
    if owner is not None:
        st.session_state.owner = owner
    st.session_state.pets = pets


def save_state() -> None:
    """Write the current owner + pets to the data file as JSON."""
    data = serialize_state(st.session_state.get("owner"), st.session_state.pets)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.markdown("Plan your pets' day by adding tasks, then generate a schedule based on available time.")

# pets is a name -> Pet registry so one owner can manage several pets.
# On first load this session, restore any previously saved state from disk.
if "pets" not in st.session_state:
    load_state()
    if "pets" not in st.session_state:
        st.session_state.pets = {}

# --- Save / load data (sidebar) ---
with st.sidebar:
    st.subheader("💾 Data")
    st.caption("Your pets and tasks are saved automatically and survive a refresh.")

    st.download_button(
        "⬇️ Download backup",
        data=json.dumps(
            serialize_state(st.session_state.get("owner"), st.session_state.pets),
            indent=2,
        ),
        file_name="pawpal_data.json",
        mime="application/json",
    )

    uploaded = st.file_uploader("⬆️ Restore from backup", type="json")
    if uploaded is not None:
        try:
            owner, pets = deserialize_state(json.loads(uploaded.getvalue()))
        except (json.JSONDecodeError, KeyError, ValueError):
            st.error("That file isn't a valid PawPal+ backup.")
        else:
            if owner is not None:
                st.session_state.owner = owner
            st.session_state.pets = pets
            save_state()
            st.success("Backup restored.")
            st.rerun()

st.divider()

# --- Owner & Pets ---
st.subheader("Owner & Pets")
col1, col2 = st.columns(2)
with col1:
    owner_name = st.text_input("Owner name", value="Jordan")
    available_minutes = st.number_input("Available time (minutes)", min_value=1, max_value=480, value=60)
with col2:
    pet_name = st.text_input("Pet name", value="Mochi")
    breed = st.text_input("Breed", value="Mixed")

bcol1, bcol2 = st.columns(2)
if bcol1.button("Save owner"):
    st.session_state.owner = Owner(name=owner_name, available_minutes=int(available_minutes))

if bcol2.button("Add / update pet"):
    pets = st.session_state.pets
    # Preserve existing tasks when an already-known pet is re-saved.
    existing_tasks = pets[pet_name].tasks if pet_name in pets else []
    pets[pet_name] = Pet(name=pet_name, breed=breed, tasks=existing_tasks)

if "owner" in st.session_state:
    st.success(f"Owner: {st.session_state.owner.name} ({st.session_state.owner.available_minutes} min available)")
if st.session_state.pets:
    st.caption("Pets: " + ", ".join(st.session_state.pets))

st.divider()

# --- Tasks (stored per pet) ---
st.subheader("Tasks")

if not st.session_state.pets:
    st.info("Add a pet first to start adding tasks.")
else:
    # The pet selector doubles as the "filter by pet name" control.
    selected_name = st.selectbox("Pet", list(st.session_state.pets))
    pet = st.session_state.pets[selected_name]

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        start_time = st.time_input("Start time", value=time(8, 0), step=300)
    with col3:
        duration = st.number_input("Duration (minutes)", min_value=1, max_value=240, value=20)
    with col4:
        priority = st.selectbox("Priority", ["high", "medium", "low"])
    with col5:
        recurrence = st.selectbox("Repeats", ["none", "daily", "weekly"])

    if st.button("Add task"):
        pet.add_task(
            Task(
                title=task_title,
                duration_minutes=int(duration),
                priority=Priority(priority),
                start_time=start_time.strftime("%H:%M"),
                recurrence=Recurrence(recurrence),
            )
        )

    if pet.tasks:
        pet.sort_tasks()

        status = st.radio("Show", ["All", "Pending", "Completed"], horizontal=True)
        if status == "Pending":
            visible = pet.filter_tasks(complete=False)
        elif status == "Completed":
            visible = pet.filter_tasks(complete=True)
        else:
            visible = pet.tasks

        st.write(f"{pet.name}'s tasks (ordered by start time) — showing {len(visible)} of {len(pet.tasks)}:")
        if not visible:
            st.caption("No tasks match this filter.")
        for t in visible:
            c0, c1, c2, c3, c4, c5, c6, c7 = st.columns([2, 3, 2, 2, 1, 1, 1, 1])
            c0.write(t.start_time)
            title = t.title
            if t.is_recurring:
                title += f"  🔁 {t.recurrence.value}"
                if t.due_date is not None:
                    title += f" (next: {t.due_date:%b %d})"
            c1.write(title)
            c2.write(f"{t.duration_minutes} min")
            priority_badge = {"high": "🔴 high", "medium": "🟡 medium", "low": "🟢 low"}
            c3.write(priority_badge[t.priority.value])
            c4.write("✅" if t.is_complete else "—")
            if not t.is_complete:
                if c5.button("✓", key=f"done_{id(t)}", help="Mark as done"):
                    new_task = pet.complete_task(t)
                    if new_task is not None:
                        st.toast(f"Queued next {t.recurrence.value} '{t.title}' for {new_task.due_date:%b %d}")
                    st.rerun()
            if c7.button("🗑️", key=f"del_{id(t)}", help="Delete task"):
                pet.remove_task(t)
                st.rerun()
            edit_key = f"editing_{id(t)}"
            if not t.is_complete and c6.button("✏️", key=f"edit_btn_{id(t)}", help="Edit task"):
                st.session_state[edit_key] = not st.session_state.get(edit_key, False)
            if not t.is_complete and st.session_state.get(edit_key, False):
                with st.expander("Edit task", expanded=True):
                    e1, e2, e3, e4, e5 = st.columns(5)
                    new_title = e1.text_input("Title", value=t.title, key=f"e_title_{id(t)}")
                    new_start = e2.time_input("Start time", value=time.fromisoformat(t.start_time), step=300, key=f"e_start_{id(t)}")
                    new_dur = e3.number_input("Duration (min)", min_value=1, max_value=240, value=t.duration_minutes, key=f"e_dur_{id(t)}")
                    new_pri = e4.selectbox("Priority", ["high", "medium", "low"], index=["high", "medium", "low"].index(t.priority.value), key=f"e_pri_{id(t)}")
                    new_rec = e5.selectbox("Repeats", ["none", "daily", "weekly"], index=["none", "daily", "weekly"].index(t.recurrence.value), key=f"e_rec_{id(t)}")
                    if st.button("Save changes", key=f"save_{id(t)}"):
                        pet.update_task(
                            t,
                            title=new_title,
                            start_time=new_start.strftime("%H:%M"),
                            duration_minutes=int(new_dur),
                            priority=Priority(new_pri),
                            recurrence=Recurrence(new_rec),
                        )
                        del st.session_state[edit_key]
                        st.rerun()

        # --- Conflict detection for the selected pet ---
        owner = st.session_state.get("owner")
        scheduler = Scheduler(pet=pet, owner=owner) if owner else None
        if scheduler:
            conflicts = scheduler.find_conflicts()
            if conflicts:
                st.warning(f"⚠️ {len(conflicts)} time conflict(s) for {pet.name}:")
                for a, b in conflicts:
                    st.markdown(
                        f"- **{a.title}** ({a.start_time}–{t_end(a)}) overlaps "
                        f"**{b.title}** ({b.start_time}–{t_end(b)})"
                    )

        if st.button("Clear all tasks"):
            for t in list(pet.tasks):
                pet.remove_task(t)
            st.rerun()
    else:
        st.info("No tasks yet. Add one above.")

# --- Owner-wide conflicts across all pets ---
if len(st.session_state.pets) > 1:
    owner_conflicts = Scheduler.find_conflicts_among(list(st.session_state.pets.values()))
    cross = [(pa, ta, pb, tb) for pa, ta, pb, tb in owner_conflicts if pa is not pb]
    if cross:
        st.warning(f"⚠️ {len(cross)} cross-pet conflict(s) — you can't care for two pets at once:")
        for pa, ta, pb, tb in cross:
            st.markdown(
                f"- {pa.name}'s **{ta.title}** ({ta.start_time}–{t_end(ta)}) overlaps "
                f"{pb.name}'s **{tb.title}** ({tb.start_time}–{t_end(tb)})"
            )

st.divider()

# --- Schedule generation ---
st.subheader("Generate Schedule")

# Scope lets the owner plan one pet's day or share the time budget across all
# pets (a single timeline where the owner can't attend two pets at once).
scope = st.radio(
    "Plan for",
    ["Selected pet", "All pets (shared time)"],
    horizontal=True,
    disabled=len(st.session_state.pets) < 2,
)

use_agent = st.checkbox(
    "🤖 Use AI to fine-tune priorities and explain this schedule",
    help="An agent may nudge a task's priority before scheduling (never saved) "
    "and writes a short explanation of the result. Falls back to the plain "
    "scheduler if no GEMINI_API_KEY is configured.",
)

if st.button("Generate schedule"):
    if "owner" not in st.session_state:
        st.warning("Save your owner info first.")
    elif not st.session_state.pets:
        st.warning("Add a pet first.")
    elif scope == "All pets (shared time)":
        owner = st.session_state.owner
        pets = list(st.session_state.pets.values())
        if use_agent:
            plan, used_agent = agent.generate_plan(pets, owner)
        else:
            plan, used_agent = Scheduler.generate_owner_plan(pets, owner), False

        if not plan:
            st.warning("No tasks fit within the available time. Try adding shorter tasks or increasing available time.")
        else:
            st.success(f"Schedule across all pets — {owner.name} has {owner.available_minutes} min available.")
            if used_agent:
                st.caption("🤖 One or more priorities were adjusted by the AI planner for this run.")
            total = 0
            for i, (p, task) in enumerate(plan, start=1):
                total += task.duration_minutes
                st.markdown(
                    f"**{i}. {task.start_time} · {p.name} — {task.title}** — "
                    f"{task.duration_minutes} min (priority: {task.priority.value})"
                )
            st.info(f"Total time scheduled: {total} min out of {owner.available_minutes} min available.")

            chosen = {id(task) for _, task in plan}
            chosen_tasks = [task for _, task in plan]
            skipped = [
                (p, t)
                for p in pets
                for t in p.pending()
                if id(t) not in chosen
            ]
            if skipped:
                st.markdown("**Skipped (no time left or conflicts with a scheduled task):**")
                for p, t in skipped:
                    reason = (
                        "overlaps a scheduled task"
                        if any(tasks_overlap(t, c) for c in chosen_tasks)
                        else "did not fit remaining time"
                    )
                    st.markdown(f"- {p.name} — {t.title} ({t.duration_minutes} min) — {reason}")
                render_overflow_hint([t for _, t in skipped], chosen_tasks)

            if use_agent:
                try:
                    st.markdown(f"**🤖 AI summary:** {agent.explain_plan(plan, skipped, owner)}")
                except AgentUnavailable as exc:
                    st.caption(f"AI explanation unavailable ({exc}).")
    else:
        owner = st.session_state.owner
        pet = st.session_state.pets[selected_name]
        if not pet.tasks:
            st.warning("Add at least one task before generating a schedule.")
        else:
            if use_agent:
                pairs, used_agent = agent.generate_plan([pet], owner)
            else:
                pairs, used_agent = [(pet, t) for t in Scheduler(pet=pet, owner=owner).generate_plan()], False
            plan = [t for _, t in pairs]

            if not plan:
                st.warning("No tasks fit within the available time. Try adding shorter tasks or increasing available time.")
            else:
                st.success(f"Schedule for {pet.name} — {owner.name} has {owner.available_minutes} min available.")
                if used_agent:
                    st.caption("🤖 One or more priorities were adjusted by the AI planner for this run.")
                total = 0
                for i, task in enumerate(plan, start=1):
                    total += task.duration_minutes
                    st.markdown(
                        f"**{i}. {task.title}** — {task.duration_minutes} min "
                        f"(priority: {task.priority.value})"
                    )
                st.info(f"Total time scheduled: {total} min out of {owner.available_minutes} min available.")

                skipped = [t for t in pet.tasks if t not in plan and not t.is_complete]
                if skipped:
                    st.markdown("**Skipped (no time left or conflicts with a scheduled task):**")
                    for t in skipped:
                        reason = (
                            "overlaps a scheduled task"
                            if any(tasks_overlap(t, p) for p in plan)
                            else "did not fit remaining time"
                        )
                        st.markdown(f"- {t.title} ({t.duration_minutes} min) — {reason}")
                    render_overflow_hint(skipped, plan)

                if use_agent:
                    try:
                        skipped_pairs = [(pet, t) for t in skipped]
                        st.markdown(f"**🤖 AI summary:** {agent.explain_plan(pairs, skipped_pairs, owner)}")
                    except AgentUnavailable as exc:
                        st.caption(f"AI explanation unavailable ({exc}).")

# Streamlit reruns this script top-to-bottom on every interaction, so saving
# here persists whatever the user just changed (added/completed/cleared tasks).
save_state()
