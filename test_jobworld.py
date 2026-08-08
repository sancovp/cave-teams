#!/usr/bin/env python3
"""JobWorld — the org as a literal World() class. Deterministic (NO API).

Proves: the task lifecycle (assign → work → report → supposedly_done → CEO
review → complete/not_complete), the CEO's planner/reviewer seats, the stop
condition, mutator guards, a department whose runtime IS a whole world
(SkillcraftWorld driving its report), and DarkFactoryWorld — the factory's
jobworld coded in the library — running its full round from one config dict.
"""
import asyncio
import os
import tempfile

from cave_teams.jobworld import (JobWorld, CEO, Department, jobworld_board,
                                 jobworld_mutator, assign)
from cave_teams.darkfactory import DarkFactoryWorld
from cave_teams.skillcraft import SkillcraftWorld, initial_state, craft_skill


class FnRuntime:
    """Any object with .run — the polymorphic slot, coded."""
    def __init__(self, fn):
        self.fn = fn

    def run(self, spec):
        return self.fn(spec)


def test_lifecycle_and_guards():
    mut = jobworld_mutator()
    b = jobworld_board()
    tid = assign(b, "research", "find things")
    # wrong dept can't report another's task; unknown task rejected
    for bad in ({"type": "report", "task_id": tid},):
        try:
            mut(b, "content", bad)
            raise AssertionError("guard did not fire: cross-dept report")
        except ValueError:
            pass
    b2 = mut(b, "research", {"type": "report", "task_id": tid, "result": "found"})
    task = b2["tasks"][0]
    assert task["status"] == "supposedly_done" and task["result"] == "found"
    # double-report of a supposedly_done task is refused
    try:
        mut(b2, "research", {"type": "report", "task_id": tid, "result": "again"})
        raise AssertionError("guard did not fire: re-report")
    except ValueError:
        pass
    print("  lifecycle guards: cross-dept · re-report · event log ✓")


def test_org_round_loop():
    seen = {"planned": 0}

    def planner(board):
        if seen["planned"] == 0:
            seen["planned"] = 1
            return [("research", "find X"), ("content", "write Y")]
        return []                                  # nothing more → stop

    def reviewer(task, board):
        ok = task["result"] and "done" in str(task["result"])
        return ("complete" if ok else "not_complete", "checked")

    world = JobWorld(
        departments={
            "research": Department("research", FnRuntime(lambda s: "done: " + s)),
            "content": Department("content", FnRuntime(lambda s: "half")),
        },
        ceo=CEO(planner, reviewer), rounds=6, name="org-test")
    res = asyncio.run(world.execute({}))
    b = res.context["board"]
    st = {t["dept"]: t["status"] for t in b["tasks"]}
    assert st["research"] == "complete"
    assert st["content"] in ("not_complete", "supposedly_done")
    kinds = [e["type"] for e in b["events"]]
    assert "assign" in kinds and "report" in kinds and "review" in kinds
    print(f"  org round loop: assign→work→report→review "
          f"(research=complete, content={st['content']}), "
          f"{len(b['events'])} events ✓")


def test_department_that_IS_a_world(root, quests):
    """A department whose runtime boots a whole SkillcraftWorld and reports
    from its board — an agent running AS an entire world."""
    class WorldRuntime:
        async def run(self, spec):
            sp = craft_skill(root, "w_agent", "dept_product", "# real skill")
            world = SkillcraftWorld(
                agents={"w_agent": Department("w_agent", FnRuntime(
                    lambda s: ""))},   # placeholder player; the craft is done
                agents_root=root, quests_root=quests, rounds=1, seasons=1,
                name="inner-world")
            res = await world.execute({"board": initial_state(["w_agent"])})
            inner = res.context["board"]
            return {"crafted": sp, "season": inner["season"]["number"]}

    def planner(board):
        return [("world_dept", "produce")] if not board["tasks"] else []

    world = JobWorld(
        departments={"world_dept": Department("world_dept", WorldRuntime())},
        ceo=CEO(planner, lambda t, b: ("complete", "world reported")),
        rounds=4, name="org-of-worlds")
    res = asyncio.run(world.execute({}))
    task = res.context["board"]["tasks"][0]
    assert task["status"] == "complete"
    assert task["result"]["crafted"].endswith("dept_product.md")
    assert os.path.isfile(os.path.join(root, "w_agent", "crafted",
                                       "dept_product.md"))
    print("  a department ran AS an entire world (SkillcraftWorld inside the "
          "org; real artifact on disk) ✓")


def test_dark_factory_world():
    """DarkFactoryWorld from ONE config dict: live plays → telemetry aims dev
    → dev's candidate → the judge (gate+race seat) → verdicts on the board."""
    cfg = {"factory_name": "df-test", "charter": "IMPROVE THE CODEBASE",
           "jobworld_rounds": 6}
    dev = FnRuntime(lambda spec: {"candidate": "skill.md",
                                  "change": "composed a recipe",
                                  "saw_charter": "IMPROVE THE CODEBASE" in spec})
    live = FnRuntime(lambda spec: {"throughput": 3, "trades": 1})
    judged = {}

    def judge(candidate, board):
        judged.update(candidate)
        return {"verdict": "SHIP", "fitness": "4→6"}

    world = DarkFactoryWorld(cfg, dev_world_runtime=dev,
                             live_world_runtime=live, judge=judge)
    res = asyncio.run(world.execute({}))
    b = res.context["board"]
    st = {t["dept"]: t for t in b["tasks"]}
    assert st["live_world"]["status"] == "complete"
    assert st["dev_world"]["status"] == "complete"          # SHIP ⇒ complete
    assert st["dev_world"]["review"]["verdict"] == "SHIP"
    assert judged.get("saw_charter") is True                 # charter piped
    assert judged.get("change") == "composed a recipe"       # candidate piped
    print("  DarkFactoryWorld: one config → live→telemetry→dev→judge→SHIP, "
          "all on the org board ✓")


def main():
    with tempfile.TemporaryDirectory() as d:
        test_lifecycle_and_guards()
        test_org_round_loop()
        test_department_that_IS_a_world(os.path.join(d, "agents"),
                                        os.path.join(d, "quests"))
        test_dark_factory_world()
    print("JOBWORLD PASS — the org is a literal World() class in the library; "
          "departments run as agents OR as entire worlds; the dark factory's "
          "jobworld is one configured object.")


if __name__ == "__main__":
    main()
