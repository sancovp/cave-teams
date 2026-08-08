"""
jobworld.py — JobWorld as a LITERAL World() class in the library.

The org as a world: a CEO + departments on a task blackboard, running the
jobworld round loop — assign → work → report → supposedly_done → CEO review
→ complete / not_complete → next assignment. One singular runtime object
that takes its config. Departments are ANY Link — an agent, or a whole world
via `world_as_agent` (some agents run AS entire worlds).

    JobWorld = blackboard( departments ↔ task-board ↔ CEO(adjudicator) )

The task lifecycle IS the mutator (the world-logic lives in the mutator, per
the blackboard law); the CEO is the adjudicator (reviews, assigns, stops).
Board shape:
    {"tasks": [{"id", "dept", "spec", "status", "result", "review"}],
     "events": [...]}                       # append-only, the org's history
status: assigned → supposedly_done → complete | not_complete (reassignable)
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .chain_ontology import Link, LinkResult, LinkStatus
from .blackboard import blackboard


def jobworld_board(tasks: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """A fresh org board. Tasks may be pre-seeded; the CEO assigns the rest."""
    return {"tasks": list(tasks or []), "events": [], "_next_task": 1}


def jobworld_mutator() -> Callable:
    """The task lifecycle as the single write path. Department actions:
      {"type": "report", "task_id": ..., "result": ...}   → supposedly_done
    Guard failures raise ValueError (logged by the arena, never crash it)."""

    def mut(state: Dict[str, Any], dept: str, action: Any) -> Dict[str, Any]:
        import json as _json
        if not isinstance(action, dict):
            raise ValueError(f"non-dict action from {dept}: {action!r}")
        s = _json.loads(_json.dumps(state))
        t = action.get("type")
        if t == "report":
            tid = action.get("task_id")
            task = next((x for x in s["tasks"] if x["id"] == tid), None)
            if task is None:
                raise ValueError(f"{dept}: no task {tid}")
            if task["dept"] != dept:
                raise ValueError(f"{dept}: task {tid} belongs to {task['dept']}")
            if task["status"] not in ("assigned", "not_complete"):
                raise ValueError(f"{dept}: task {tid} is {task['status']}")
            task["status"] = "supposedly_done"
            task["result"] = action.get("result")
            s["events"].append({"type": "report", "dept": dept, "task": tid})
        else:                                    # wait/idle etc. — event only
            s["events"].append({"type": t or "noop", "dept": dept})
        return s

    return mut


def assign(board: Dict[str, Any], dept: str, spec: Any) -> str:
    """CEO-side helper: put a task on the board (the CEO owns assignment)."""
    tid = f"task_{board.get('_next_task', 1)}"
    board["_next_task"] = board.get("_next_task", 1) + 1
    board["tasks"].append({"id": tid, "dept": dept, "spec": spec,
                           "status": "assigned", "result": None,
                           "review": None})
    board["events"].append({"type": "assign", "dept": dept, "task": tid})
    return tid


def review(board: Dict[str, Any], task_id: str, verdict: str,
           note: Any = None) -> None:
    """CEO-side helper: rule on a supposedly_done task."""
    if verdict not in ("complete", "not_complete"):
        raise ValueError("verdict must be complete|not_complete")
    for task in board["tasks"]:
        if task["id"] == task_id:
            task["status"] = verdict
            task["review"] = note
    board["events"].append({"type": "review", "task": task_id,
                            "verdict": verdict})


class Department(Link):
    """A department seat: finds ITS assigned tasks on the board and hands the
    oldest one to its runtime (`.run(spec_str) -> result_str` — ANY runtime:
    an LLM, a coded fn wrapped in Runtime, or a whole world's driver)."""

    def __init__(self, name: str, runtime: Any):
        self.name = name
        self.runtime = runtime

    async def execute(self, ctx=None, **_):
        import inspect, json as _json
        c = dict(ctx or {})
        board = c.get("board", {})
        mine = [t for t in board.get("tasks", [])
                if t["dept"] == self.name
                and t["status"] in ("assigned", "not_complete")]
        if not mine:
            c["action"] = {"type": "wait"}
            return LinkResult(status=LinkStatus.SUCCESS, context=c)
        task = mine[0]
        spec = task["spec"] if isinstance(task["spec"], str) \
            else _json.dumps(task["spec"])
        out = self.runtime.run(spec)
        if inspect.isawaitable(out):
            out = await out
        c["action"] = {"type": "report", "task_id": task["id"], "result": out}
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class CEO(Link):
    """The CEO seat (the blackboard's adjudicator): each round it REVIEWS
    every supposedly_done task via `reviewer(task, board) -> (verdict, note)`
    and ASSIGNS next work via `planner(board) -> [(dept, spec), ...]`.
    Sets board['_stop'] when planner returns nothing and nothing is pending.
    Both seats are pluggable — coded procedures or LLM-backed callables."""
    name = "ceo"

    def __init__(self, planner: Callable, reviewer: Callable):
        self.planner = planner
        self.reviewer = reviewer

    async def execute(self, ctx=None, **_):
        import inspect
        c = dict(ctx or {})
        b = dict(c.get("board", {}))
        for task in [t for t in b.get("tasks", [])
                     if t["status"] == "supposedly_done"]:
            out = self.reviewer(task, b)
            if inspect.isawaitable(out):
                out = await out
            verdict, note = out
            review(b, task["id"], verdict, note)
        out = self.planner(b)
        if inspect.isawaitable(out):
            out = await out
        for dept, spec in (out or []):
            assign(b, dept, spec)
        pending = any(t["status"] in ("assigned", "not_complete",
                                      "supposedly_done")
                      for t in b.get("tasks", []))
        if not out and not pending:
            b["_stop"] = True
        c["board"] = b
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class JobWorld(Link):
    """THE World() class: instantiate with the org (CEO + departments) and a
    config; run it; the board is the org's state. Departments are any Link —
    including `world_as_agent(...)`: an agent whose runtime IS a world."""

    def __init__(self, departments: Dict[str, Link], ceo: CEO,
                 rounds: int = 8, name: str = "jobworld",
                 state_key: str = "board"):
        self.name = name
        self.state_key = state_key
        self.arena = blackboard(departments, jobworld_mutator(),
                                adjudicator=ceo, rounds=rounds,
                                state_key=state_key, name=f"{name}:org")

    async def execute(self, context=None, **_):
        ctx = dict(context or {})
        ctx.setdefault(self.state_key, jobworld_board())
        return await self.arena.execute(ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'JobWorld "{self.name}":\n' \
            + self.arena.describe(depth + 1)


__all__ = ["JobWorld", "CEO", "Department", "jobworld_board",
           "jobworld_mutator", "assign", "review"]
