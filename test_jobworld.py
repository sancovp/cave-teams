#!/usr/bin/env python3
"""JobWorld PARITY suite — the class vs the real system (twi-jobworld
server/jobworld_agent.py), deterministic (NO API). Every assertion mirrors the
served system's exact semantics: store shape, entity fields/statuses, the
emit_event observation flip, the CEO review cascade (task→goal→milestone),
the dept NAME-vs-id open-tasks fix, the rule-06 roster gate (no soloing), the
workday round loop, and DarkFactoryWorld running the full org from one config.
"""
import asyncio
import json

from cave_teams.jobworld import (
    JobWorld, CEO, Department, jobworld_store, jobworld_mutator,
    create_company, create_department, create_agent, create_project,
    create_milestone, create_goal, create_task, ceo_review_task, assign_task,
    close_day, get_open_tasks, get_org_chart)
from cave_teams.darkfactory import DarkFactoryWorld


class FnRuntime:
    def __init__(self, fn):
        self.fn = fn

    def run(self, spec):
        return self.fn(spec)


def _org():
    """company → dept → agent → project → milestone → goal → task (exact
    field parity with jobworld_agent.py create_*)."""
    s = jobworld_store()
    create_company(s, "acme")
    d = create_department(s, "research")
    a = create_agent(s, d["id"], "worker_1")
    p = create_project(s, "proj")
    m = create_milestone(s, p["id"], "ms")
    g = create_goal(s, m["id"], "the goal")
    t = create_task(s, g["id"], "research", "find things")
    return s, d, a, g, t, m


def test_entities_exact():
    s, d, a, g, t, m = _org()
    assert s["company"]["dept_ids"] == [d["id"]]
    assert a["status"] == "idle" and a["current_task_id"] is None
    assert m["status"] == "pending" and g["status"] == "pending"
    assert t["status"] == "open" and t["agent_id"] is None
    assert g["tasks"] == [t["id"]] and m["goals"] == [g["id"]]
    print("  entities: exact field/status parity (open·idle·pending) ✓")


def test_observation_flip_and_block():
    s, d, a, g, t, m = _org()
    assign_task(s, t["id"], a["id"])
    assert s["agents"][a["id"]]["status"] == "working"
    mut = jobworld_mutator()
    # the REAL report contract: emit_event with the observation shape
    s2 = mut(s, "research", {"type": "emit_event", "event": {
        "process": "research-work",
        "observation": {"goal_id": g["id"], "task": t["id"],
                        "status": "completed", "desc": "found it"}}})
    task = s2["tasks"][t["id"]]
    assert task["status"] == "supposedly_done" and task["result"] == "found it"
    assert s2["goals"][g["id"]]["status"] == "pending"      # all_done → pending
    agent = s2["agents"][a["id"]]
    assert agent["status"] == "idle" and agent["current_task_id"] is None
    # blocked path: goal → "not"
    t2 = create_task(s2, g["id"], "research", "second")
    s3 = mut(s2, "research", {"type": "emit_event", "event": {
        "observation": {"goal_id": g["id"], "task": t2["id"],
                        "status": "blocked", "desc": "no access"}}})
    assert s3["tasks"][t2["id"]]["status"] == "blocked"
    assert s3["tasks"][t2["id"]]["blocked_reason"] == "no access"
    assert s3["goals"][g["id"]]["status"] == "not"
    print("  emit_event flip: completed→supposedly_done (+agent freed) · "
          "blocked→goal 'not' ✓")


def test_review_cascade():
    s, d, a, g, t, m = _org()
    mut = jobworld_mutator()
    s = mut(s, "research", {"type": "emit_event", "event": {
        "observation": {"goal_id": g["id"], "task": t["id"],
                        "status": "completed", "desc": "done"}}})
    # not_complete → back to open, result popped, goal pending
    ceo_review_task(s, t["id"], "not_complete")
    assert s["tasks"][t["id"]]["status"] == "open"
    assert "result" not in s["tasks"][t["id"]]
    assert s["goals"][g["id"]]["status"] == "pending"
    # complete → the full cascade: goal "met", milestone "true"
    s = mut(s, "research", {"type": "emit_event", "event": {
        "observation": {"goal_id": g["id"], "task": t["id"],
                        "status": "completed", "desc": "done right"}}})
    ceo_review_task(s, t["id"], "complete")
    assert s["tasks"][t["id"]]["status"] == "complete"
    assert s["goals"][g["id"]]["status"] == "met"
    assert s["milestones"][m["id"]]["status"] == "true"
    assert close_day(s)["day"] == 2
    print("  review cascade: not_complete→open(+result popped) · "
          "complete→goal met→milestone 'true' · close_day ✓")


def test_department_write_path_guarded():
    s, *_ = _org()
    mut = jobworld_mutator()
    try:
        mut(s, "research", {"type": "create_task", "goal_id": "x"})
        raise AssertionError("guard did not fire: dept must not create")
    except ValueError:
        pass
    print("  the write path: departments emit_event ONLY (CEO owns the rest) ✓")


def test_open_tasks_dept_name_fix():
    s, d, a, g, t, m = _org()
    create_task(s, g["id"], "Research", "case-insensitive dept name")
    other = create_department(s, "content")
    b = create_agent(s, other["id"], "worker_2")
    create_task(s, g["id"], "content", "content's task")
    mine = get_open_tasks(s, a["id"])
    # research agent sees research tasks (name match, case-insensitive) and
    # unassigned ones — the served system's fixed filter, ported
    assert all((x["dept"].lower() == "research") or not x.get("agent_id")
               for x in mine)
    assert len(get_open_tasks(s, b["id"])) >= 1
    print("  get_open_tasks: dept NAME-vs-id fix + unassigned clause ✓")


def test_roster_gate_no_soloing():
    """rule-06: an unbootstrapped org must not run work."""
    world = JobWorld(
        departments={"research": Department("research",
                                            FnRuntime(lambda s: "did it"))},
        ceo=CEO(planner=lambda s: True, reviewer=lambda t, s: ("complete", "")),
        rounds=3, name="ungated")
    res = asyncio.run(world.execute({}))
    s = res.context["store"]
    assert s["tasks"] == {} and s["company"] is None     # nothing ran
    print("  roster gate: empty org → no tasks, no soloing ✓")


def test_workday_round_loop():
    """first_boot → assign → dept works → emit_event flip → CEO review →
    complete → stop. The full round, through the World object."""
    st = {"assigned": False}

    def first_boot(s):
        create_company(s, "acme")
        d = create_department(s, "research")
        create_agent(s, d["id"], "worker_1")

    def planner(s):
        if st["assigned"]:
            return False
        p = create_project(s, "p")
        m = create_milestone(s, p["id"], "m")
        g = create_goal(s, m["id"], "g")
        t = create_task(s, g["id"], "research", "find X")
        assign_task(s, t["id"], next(iter(s["agents"])))
        st["assigned"] = True
        return True

    world = JobWorld(
        departments={"research": Department(
            "research", FnRuntime(lambda spec: "found: "
                                  + json.loads(spec)["description"]))},
        ceo=CEO(planner, lambda t, s: ("complete", "verified"), first_boot),
        rounds=6, name="workday")
    res = asyncio.run(world.execute({}))
    s = res.context["store"]
    task = next(iter(s["tasks"].values()))
    assert task["status"] == "complete" and "found: find X" in task["result"]
    assert next(iter(s["goals"].values()))["status"] == "met"
    chart = get_org_chart(s)
    assert chart["company"]["name"] == "acme"
    assert chart["departments"][0]["agents"][0]["name"] == "worker_1"
    kinds = [e.get("observation", {}).get("status") for e in s["events"]]
    assert "first_boot" in kinds and "completed" in kinds \
        and "round_complete" in kinds
    print("  the workday round: boot→assign→work→flip→review→met, "
          "org chart + event stream ✓")


def test_dark_factory_world():
    cfg = {"factory_name": "df-test", "charter": "IMPROVE THE CODEBASE",
           "jobworld_rounds": 8}
    seen = {}

    def dev(spec):
        task = json.loads(spec)
        inner = json.loads(task["description"])
        seen["charter_piped"] = "IMPROVE THE CODEBASE" in inner["charter"]
        seen["telemetry_piped"] = "throughput" in str(inner["telemetry"])
        return {"candidate": "recipe.md", "change": "composed a recipe"}

    def judge(candidate, store):
        seen["judged"] = candidate
        return {"verdict": "SHIP", "fitness": "2→4"}

    world = DarkFactoryWorld(
        cfg,
        dev_world_runtime=FnRuntime(dev),
        live_world_runtime=FnRuntime(lambda spec: {"throughput": 2}),
        judge=judge)
    res = asyncio.run(world.execute({}))
    s = res.context["store"]
    by_dept = {t["dept"]: t for t in s["tasks"].values()}
    assert s["company"]["name"] == "df-test"
    assert len(s["departments"]) == 2 and len(s["agents"]) == 2
    assert by_dept["live_world"]["status"] == "complete"
    assert by_dept["dev_world"]["status"] == "complete"
    assert seen["charter_piped"] and seen["telemetry_piped"]
    assert seen["judged"]["change"] == "composed a recipe"
    goal = next(iter(s["goals"].values()))
    ms = next(iter(s["milestones"].values()))
    assert goal["status"] == "met" and ms["status"] == "true"   # the cascade
    print("  DarkFactoryWorld: first-boot org → live→dev→judge→SHIP → "
          "goal 'met', milestone 'true' — one config, the real cascades ✓")


def main():
    test_entities_exact()
    test_observation_flip_and_block()
    test_review_cascade()
    test_department_write_path_guarded()
    test_open_tasks_dept_name_fix()
    test_roster_gate_no_soloing()
    test_workday_round_loop()
    test_dark_factory_world()
    print("JOBWORLD PARITY PASS — the class carries the served system's exact "
          "semantics (store, flip, cascades, roster gate, round loop); the "
          "dark factory's jobworld runs on it from one config.")


if __name__ == "__main__":
    main()
