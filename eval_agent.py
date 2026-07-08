"""Reliability / consistency eval harness for the PawPal+ agent (agent.py).

The agentic layer is non-deterministic (an LLM decides the priority overrides
and writes the explanation), so unit tests can only pin down its *guardrails*,
not its *quality*. This script measures the parts a test suite can't:

  1. Consistency  -- run the same request N times and see how often the agent
     returns the SAME priority overrides. A wildly different answer every run
     is a red flag for a scheduler an owner is meant to trust.
  2. Reliability  -- confirm the agent's guarantee actually holds: every plan
     it produces is conflict-free and within the owner's time budget, on every
     run, no matter what the LLM suggested.
  3. Grounding    -- run explain_plan N times and count how often the anti-
     hallucination check accepts the explanation (it references a real task).

Run it:

    python eval_agent.py            # uses real Gemini if GEMINI_API_KEY is set
    python eval_agent.py --runs 10  # more samples per scenario

Without a GEMINI_API_KEY it drops into a clearly-labelled SIMULATED mode so the
report format is still demonstrable offline (no real API calls, canned answers).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from typing import Callable, Dict, List, Optional, Tuple

import agent
from agent import AgentUnavailable
from pawpal_system import Owner, Pet, Priority, Task, tasks_overlap


# --- Scenarios ---------------------------------------------------------------

def _scenarios() -> List[Tuple[str, List[Pet], Owner]]:
    """Fixed scenarios the eval runs against (deterministic inputs)."""
    # Scenario A: a medical task is under-prioritized relative to grooming and
    # they clash -- the agent *should* consistently bump the medical one.
    buddy = Pet(name="Buddy", breed="Golden Retriever")
    buddy.add_task(Task("Vet visit", 30, Priority.LOW, start_time="09:00"))
    buddy.add_task(Task("Grooming", 30, Priority.MEDIUM, start_time="09:00"))
    owner_a = Owner(name="Alex", available_minutes=30)

    # Scenario B: two pets, tight budget -- a good override must not starve one.
    milo = Pet(name="Milo", breed="Beagle")
    milo.add_task(Task("Medicine", 20, Priority.LOW, start_time="08:00"))
    nala = Pet(name="Nala", breed="Tabby")
    nala.add_task(Task("Litter clean", 15, Priority.HIGH, start_time="08:00"))
    owner_b = Owner(name="Sam", available_minutes=20)

    return [
        ("A: medical vs grooming clash", [buddy], owner_a),
        ("B: two pets, shared 20 min", [milo, nala], owner_b),
    ]


# --- Pure metric helpers (unit-tested in test/test_eval.py) ------------------

def canonical(overrides: Dict[str, str]) -> str:
    """Order-independent string form of an override dict, for comparing runs."""
    return json.dumps(overrides, sort_keys=True)


def consistency_report(results: List[Dict[str, str]]) -> dict:
    """Summarize how consistent a list of per-run override dicts is.

    Returns the run count, number of distinct outcomes, the agreement rate
    (fraction of runs that match the single most common outcome), and, for each
    key that ever appeared, the fraction of runs whose value equalled that
    key's most common value ("per-key stability").
    """
    runs = len(results)
    if runs == 0:
        return {"runs": 0, "unique_outcomes": 0, "agreement_rate": 1.0, "per_key_stability": {}}

    shapes = Counter(canonical(r) for r in results)
    _, top_count = shapes.most_common(1)[0]

    all_keys = {k for r in results for k in r}
    per_key_stability: Dict[str, float] = {}
    for key in sorted(all_keys):
        values = Counter(r.get(key, "<absent>") for r in results)
        per_key_stability[key] = values.most_common(1)[0][1] / runs

    return {
        "runs": runs,
        "unique_outcomes": len(shapes),
        "agreement_rate": top_count / runs,
        "per_key_stability": per_key_stability,
    }


def plan_is_valid(plan: List[Tuple[Pet, Task]], owner: Owner) -> bool:
    """True if a plan respects the owner's budget and has no overlapping tasks.

    This is the invariant the whole design promises: no matter what the LLM
    suggests, the plan the agent returns is always schedulable.
    """
    total = sum(task.duration_minutes for _, task in plan)
    if total > owner.available_minutes:
        return False
    tasks = [task for _, task in plan]
    for i, a in enumerate(tasks):
        for b in tasks[i + 1:]:
            if tasks_overlap(a, b):
                return False
    return True


# --- Simulated _call for offline runs ----------------------------------------

def _install_simulated_call() -> None:
    """Patch agent._call with a canned, deterministic-ish stub (no API key).

    It rotates through a few plausible answers so the report shows a realistic
    (imperfect) consistency figure rather than a trivial 100%.
    """
    state = {"n": 0}
    canned = [
        '{"Buddy::Vet visit": "high"}',
        '{"Buddy::Vet visit": "high"}',
        '{"Buddy::Vet visit": "medium"}',  # the "off" answer, to vary consistency
        "Buddy's Vet visit is scheduled at 09:00 -- an important checkup.",
    ]

    def fake_call(system: str, user: str) -> str:
        # Explanation prompts ask for prose; override prompts ask for JSON.
        if "explain" in system.lower() or "sentences" in system.lower():
            # Echo a real task title from the prompt so the grounding check
            # passes for whichever scenario is running (mirrors a live pass).
            for line in user.splitlines():
                seg = line.strip()
                if seg.startswith("- ") and "—" in seg:
                    title = seg[2:].split("—", 1)[1].split("(")[0].strip()
                    return f"Today's plan centers on {title}; the rest can wait."
            return "The schedule looks good today."
        state["n"] += 1
        return canned[state["n"] % 3]  # cycle only the JSON answers

    agent._call = fake_call


# --- Eval passes -------------------------------------------------------------

def run_consistency(label: str, pets: List[Pet], owner: Owner, runs: int) -> dict:
    results = [agent.suggest_priority_overrides(pets, owner) for _ in range(runs)]
    report = consistency_report(results)
    report["label"] = label
    report["sample_outcome"] = results[0] if results else {}
    return report


def run_reliability(pets: List[Pet], owner: Owner, runs: int) -> dict:
    valid = 0
    used_agent_count = 0
    for _ in range(runs):
        plan, used_agent = agent.generate_plan(pets, owner)
        used_agent_count += int(used_agent)
        valid += int(plan_is_valid(plan, owner))
    return {"runs": runs, "valid_plans": valid, "used_agent": used_agent_count}


def run_grounding(pets: List[Pet], owner: Owner, runs: int) -> dict:
    plan, _ = agent.generate_plan(pets, owner)
    chosen = {id(t) for _, t in plan}
    skipped = [(p, t) for p in pets for t in p.pending() if id(t) not in chosen]
    accepted = 0
    for _ in range(runs):
        try:
            agent.explain_plan(plan, skipped, owner)
            accepted += 1
        except AgentUnavailable:
            pass
    return {"runs": runs, "accepted": accepted}


# --- Reporting ---------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Eval the PawPal+ agent's consistency & reliability.")
    parser.add_argument("--runs", type=int, default=5, help="samples per scenario (default 5)")
    args = parser.parse_args(argv)

    simulated = not os.environ.get("GEMINI_API_KEY")
    if simulated:
        _install_simulated_call()

    bar = "=" * 60
    print(bar)
    print("  PawPal+ Agent Eval" + ("   [SIMULATED -- no GEMINI_API_KEY]" if simulated else "   [LIVE Gemini]"))
    print(f"  {args.runs} runs per scenario")
    print(bar)

    all_valid = True
    for label, pets, owner in _scenarios():
        print(f"\n--- Scenario {label} ---")

        c = run_consistency(label, pets, owner, args.runs)
        print(f"  Consistency : {c['agreement_rate']:.0%} agreement "
              f"({c['unique_outcomes']} distinct outcome(s) over {c['runs']} runs)")
        print(f"    sample override: {c['sample_outcome'] or '{}'}")
        for key, stab in c["per_key_stability"].items():
            print(f"    key stability : {key} -> {stab:.0%}")

        r = run_reliability(pets, owner, args.runs)
        ok = r["valid_plans"] == r["runs"]
        all_valid = all_valid and ok
        flag = "OK" if ok else "FAIL"
        print(f"  Reliability : {r['valid_plans']}/{r['runs']} plans valid "
              f"(conflict-free & in budget)  [{flag}]")
        print(f"    agent adjusted priorities in {r['used_agent']}/{r['runs']} runs")

        g = run_grounding(pets, owner, args.runs)
        print(f"  Grounding   : {g['accepted']}/{g['runs']} explanations passed the "
              f"anti-hallucination check")

    print("\n" + bar)
    verdict = "PASS -- every plan was valid" if all_valid else "FAIL -- an invalid plan slipped through"
    print(f"  Reliability invariant: {verdict}")
    print(bar)
    return 0 if all_valid else 1


if __name__ == "__main__":
    sys.exit(main())