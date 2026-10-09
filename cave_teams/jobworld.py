"""
jobworld.py — JobWorld as a literal World() class, PORTED FAITHFULLY from the
real system (twi-jobworld `server/jobworld_agent.py`, the WoS-port method:
semantics line-for-line, never re-invented).

    JobWorld = blackboard( departments ↔ THE STORE ↔ CEO(adjudicator) )

What is ported EXACTLY from JobworldAgent:
  * THE STORE — the identical shape: company · departments · agents ·
    projects · milestones · goals · tasks · day · day_started_at (+
    activeFlows/sops/sop_patterns kept as slots). Board key: "store".
  * ENTITY CREATION — create_company/department/agent/project/milestone/
    goal/task with the identical field dicts and statuses (task: open,
    milestone: pending, goal: pending, agent: idle).
  * THE REPORT CONTRACT — departments write ONLY via `emit_event`
    (jobworld-report-event): observation {goal_id, task, status, desc} →
    _process_observation: completed → task supposedly_done + result; blocked
    → blocked + blocked_reason; goal recalc (all done → "pending", any
    blocked → "not"); the agent freed (idle, current_task_id None).
  * CEO REVIEW — ceo_review_task(decision): complete → "complete", else back
    to "open" (result popped); the cascade: goal all-complete → "met" / any
    blocked → "not" / else "pending"; milestone all-met → "true" / any not →
    "false".
  * assign_task · close_day · get_open_tasks (incl. the dept NAME-vs-id fix,
    sort by created_at, cap 3) · get_org_chart · get_projects_tree ·
    DOMAIN_ENUM.
  * THE WORKDAY ROUND (ceo-bootstrap): step 0 THE ROSTER GATE — an org with
    no registered departments/agents refuses to run work (first boot only;
    rule-06's no-soloing law); 1 read events; 2 review supposedly_done;
    3 assign; 4 the departments run (the arena round); 6 the round record
    event.

Deliberate substitutions (the port notes, same style as skillcraft.py):
  * ids: `time.time()*1000` → a store nonce (deterministic, collision-free —
    the real one can collide within 1ms).
  * events.jsonl → store["events"] (append-only list on the board); the
    data.json/events.jsonl SPLIT is the server's persistence layer, which
    stays with the deployment (the game.json pattern — the caller persists).
NOT PORTED YET (server-layer, flagged honest): the SOP engine
(_accumulate_sop_pattern/harvest_sop), heartbeat/broadcast/automations/
calendar/blockages — those live with the served deployment, not the world
semantics. Port the SOP engine in a second pass if wanted in-library.
"""
from __future__ import annotations

import json
from typing import Any, Callable, Dict, List, Optional

from .chain_ontology import Link, LinkResult, LinkStatus
from .blackboard import blackboard

# Business domain enum — ported verbatim (jobworld_agent.py:30)
DOMAIN_ENUM = [
    "ops", "sales", "marketing", "engineering", "finance",
    "hr", "legal", "admin", "research", "content",
    "growth", "support", "bi", "product",
]


# ── THE STORE (jobworld_agent.py:49-62, exact shape; board key "store") ──────
def jobworld_store() -> Dict[str, Any]:
    return {
        "company": None,
        "departments": {},
        "agents": {},
        "projects": {},
        "milestones": {},
        "goals": {},
        "tasks": {},
        "day": 1,
        "day_started_at": None,
        "activeFlows": {},
        "sops": {},
        "sop_patterns": {},
        "events": [],          # events.jsonl, on the board (port note above)
        "_nonce": 0,
    }


def _nid(s: Dict[str, Any], kind: str) -> str:
    s["_nonce"] = int(s.get("_nonce", 0)) + 1
    return f"{kind}-{s['_nonce']}"


# ── ENTITY CREATION (jobworld_agent.py:252-358 — identical field dicts) ──────
def create_company(s, name: str) -> dict:
    company = {"id": _nid(s, "company"), "name": name,
               "dept_ids": [], "project_ids": []}
    s["company"] = company
    return company


def create_department(s, name: str) -> dict:
    dept = {"id": _nid(s, "dept"), "name": name, "agents": []}
    s["departments"][dept["id"]] = dept
    if s["company"]:
        s["company"]["dept_ids"].append(dept["id"])
    return dept


def create_agent(s, dept_id: str, name: str, agent_file_path: str = "") -> dict:
    agent = {"id": _nid(s, "agent"), "dept_id": dept_id, "name": name,
             "status": "idle", "current_task_id": None,
             "agent_file_path": agent_file_path}
    s["agents"][agent["id"]] = agent
    dept = s["departments"].get(dept_id)
    if dept:
        dept["agents"].append(agent["id"])
    return agent


def create_project(s, name: str, description: str = "") -> dict:
    project = {"id": _nid(s, "project"), "name": name,
               "description": description, "milestones": []}
    s["projects"][project["id"]] = project
    if s["company"]:
        s["company"]["project_ids"].append(project["id"])
    return project


def create_milestone(s, project_id: str, description: str,
                     deadline: str = "") -> dict:
    milestone = {"id": _nid(s, "milestone"), "project_id": project_id,
                 "description": description, "deadline": deadline,
                 "status": "pending", "goals": []}
    s["milestones"][milestone["id"]] = milestone
    project = s["projects"].get(project_id)
    if project:
        project["milestones"].append(milestone["id"])
    return milestone


def create_goal(s, milestone_id: str, description: str) -> dict:
    goal = {"id": _nid(s, "goal"), "milestone_id": milestone_id,
            "description": description, "status": "pending", "tasks": []}
    s["goals"][goal["id"]] = goal
    milestone = s["milestones"].get(milestone_id)
    if milestone:
        milestone["goals"].append(goal["id"])
    return goal


def create_task(s, goal_id: str, dept: str, description: str) -> dict:
    task = {"id": _nid(s, "task"), "goal_id": goal_id, "dept": dept,
            "agent_id": None, "description": description, "status": "open"}
    s["tasks"][task["id"]] = task
    goal = s["goals"].get(goal_id)
    if goal:
        goal["tasks"].append(task["id"])
    return task


# ── EVENT PROCESSING (jobworld_agent.py:364-433 — the flip, line-for-line) ───
def _process_observation(s: Dict[str, Any], event: dict) -> None:
    obs = event.get("observation", {}) or {}
    goal = s["goals"].get(obs.get("goal_id"))
    task = s["tasks"].get(obs.get("task"))
    status = obs.get("status")
    if not goal or not task:
        return
    if status == "completed":
        task["status"] = "supposedly_done"
        task["result"] = obs.get("desc", "")
    elif status == "blocked":
        task["status"] = "blocked"
        task["blocked_reason"] = obs.get("desc", "")
    goal_tasks = [s["tasks"].get(t) for t in goal["tasks"] if s["tasks"].get(t)]
    all_done = goal_tasks and all(t["status"] in ("supposedly_done", "complete")
                                  for t in goal_tasks)
    any_blocked = any(t["status"] == "blocked" for t in goal_tasks)
    if all_done and not any_blocked:
        goal["status"] = "pending"
    elif any_blocked:
        goal["status"] = "not"
    if status == "completed" and task.get("agent_id"):
        agent = s["agents"].get(task["agent_id"])
        if agent:
            agent["status"] = "idle"
            agent["current_task_id"] = None


def jobworld_mutator() -> Callable:
    """The single write path for DEPARTMENTS: `emit_event` ONLY (the
    jobworld-report-event contract — workers self-report observations; every
    other verb belongs to the CEO seat, exactly like the served system where
    departments hit /api/emit-event and the CEO holds the rest)."""

    def mut(state: Dict[str, Any], dept: str, action: Any) -> Dict[str, Any]:
        if not isinstance(action, dict):
            raise ValueError(f"non-dict action from {dept}: {action!r}")
        s = json.loads(json.dumps(state))
        t = action.get("type")
        if t == "emit_event":
            event = dict(action.get("event") or {})
            if s.get("company"):
                event.setdefault("business", s["company"]["name"])
            obs = event.get("observation", {}) or {}
            if obs.get("domain") and obs["domain"] not in DOMAIN_ENUM:
                event["_domain_warning"] = f"unknown domain {obs['domain']}"
            event["dept"] = dept
            s["events"].append(event)
            _process_observation(s, event)
        elif t in ("wait", "noop", None):
            pass
        else:
            raise ValueError(f"{dept}: departments write via emit_event only "
                             f"(got {t!r})")
        return s

    return mut


# ── CEO-SIDE VERBS (jobworld_agent.py:813-890, exact cascades) ───────────────
def ceo_review_task(s, task_id: str, decision: str) -> Optional[dict]:
    task = s["tasks"].get(task_id)
    if not task:
        return None
    if decision == "complete":
        task["status"] = "complete"
    else:
        task["status"] = "open"
        task.pop("result", None)
    goal = s["goals"].get(task.get("goal_id"))
    if goal:
        goal_tasks = [s["tasks"].get(t) for t in goal["tasks"]
                      if s["tasks"].get(t)]
        all_complete = goal_tasks and all(t["status"] == "complete"
                                          for t in goal_tasks)
        any_blocked = any(t["status"] == "blocked" for t in goal_tasks)
        if all_complete and not any_blocked:
            goal["status"] = "met"
        elif any_blocked:
            goal["status"] = "not"
        else:
            goal["status"] = "pending"
        milestone = s["milestones"].get(goal.get("milestone_id"))
        if milestone:
            ms_goals = [s["goals"].get(g) for g in milestone["goals"]
                        if s["goals"].get(g)]
            if ms_goals and all(g["status"] == "met" for g in ms_goals):
                milestone["status"] = "true"
            elif any(g["status"] == "not" for g in ms_goals):
                milestone["status"] = "false"
    return task


def assign_task(s, task_id: str, agent_id: str) -> Optional[dict]:
    task = s["tasks"].get(task_id)
    agent = s["agents"].get(agent_id)
    if not task or not agent:
        return None
    task["agent_id"] = agent_id
    task["status"] = "open"
    agent["current_task_id"] = task_id
    agent["status"] = "working"
    return {"task": task, "agent": agent}


def close_day(s) -> dict:
    s["day"] += 1
    return {"day": s["day"]}


# ── QUERIES (jobworld_agent.py:854-947, incl. the dept NAME-vs-id fix) ───────
def get_open_tasks(s, agent_id: str = None) -> List[dict]:
    open_tasks = [t for t in s["tasks"].values() if t["status"] == "open"]
    if agent_id:
        agent = s["agents"].get(agent_id)
        if agent:
            dept = s["departments"].get(agent.get("dept_id")) or {}
            dept_name = (dept.get("name") or "").strip().lower()
            open_tasks = [
                t for t in open_tasks
                if (t.get("dept") or "").strip().lower() == dept_name
                or t.get("dept") == agent.get("dept_id")
                or not t.get("agent_id")
            ]
    return sorted(open_tasks, key=lambda t: t["id"])[:3]


def get_org_chart(s) -> dict:
    goals_by_dept: Dict[str, list] = {}
    for goal in s["goals"].values():
        goal_tasks = [s["tasks"].get(t) for t in goal.get("tasks", [])
                      if s["tasks"].get(t)]
        dept_name = goal_tasks[0]["dept"] if goal_tasks else "Unassigned"
        goals_by_dept.setdefault(dept_name, []).append(
            {"id": goal["id"], "description": goal["description"],
             "status": goal["status"]})
    departments = []
    for dept in s["departments"].values():
        agents = [s["agents"].get(a) for a in dept.get("agents", [])
                  if s["agents"].get(a)]
        departments.append({
            "id": dept["id"], "name": dept["name"],
            "agents": [{"id": a["id"], "name": a["name"],
                        "status": a["status"],
                        "current_task_id": a.get("current_task_id")}
                       for a in agents],
            "goals": goals_by_dept.get(dept["name"], []),
        })
    return {"company": ({"id": s["company"]["id"],
                         "name": s["company"]["name"]}
                        if s["company"] else None),
            "ceo": {"id": "ceo", "name": "CEO", "active": True},
            "departments": departments}


# ── THE DEPARTMENT SEAT ──────────────────────────────────────────────────────
class Department(Link):
    """A department: finds ITS open task on the store (the real dept-name
    scoping) and hands it to its runtime (`.run(spec)->result` — ANY runtime,
    including a whole world). Reports via emit_event with the REAL observation
    shape — the jobworld-report-event contract."""

    def __init__(self, name: str, runtime: Any):
        self.name = name
        self.runtime = runtime

    async def execute(self, ctx=None, **_):
        import inspect
        c = dict(ctx or {})
        s = c.get("store", {})
        mine = [t for t in s.get("tasks", {}).values()
                if (t.get("dept") or "").strip().lower() == self.name.lower()
                and t["status"] == "open"]
        if not mine:
            c["action"] = {"type": "wait"}
            return LinkResult(status=LinkStatus.SUCCESS, context=c)
        task = sorted(mine, key=lambda t: t["id"])[0]
        spec = json.dumps({"task_id": task["id"], "goal_id": task["goal_id"],
                           "description": task["description"]})
        out = self.runtime.run(spec)
        if inspect.isawaitable(out):
            out = await out
        desc = out if isinstance(out, str) else json.dumps(out)
        c["action"] = {"type": "emit_event", "event": {
            "process": f"{self.name}-work",
            "observation": {"goal_id": task["goal_id"], "task": task["id"],
                            "status": "completed", "desc": desc}}}
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


# ── THE CEO SEAT (the workday round — ceo-bootstrap steps) ───────────────────
class CEO(Link):
    """The adjudicator running THE WORKDAY ROUND each arena round:
      0  ROSTER GATE — no departments/agents registered ⇒ `first_boot(store)`
         only (rule-06: an unbootstrapped world must never solo the work);
      1  read events (the store IS the event stream);
      2  review every supposedly_done via `reviewer(task, store) ->
         (decision, note)` → the real ceo_review_task cascade;
      3  `planner(store) -> bool` assigns next work with the CEO-side verbs
         (create_*/assign_task) — returns True if it planned anything;
      6  the round record event; stop when nothing pending and nothing planned.
    """
    name = "ceo"

    def __init__(self, planner: Callable, reviewer: Callable,
                 first_boot: Optional[Callable] = None):
        self.planner = planner
        self.reviewer = reviewer
        self.first_boot = first_boot

    async def execute(self, ctx=None, **_):
        import inspect

        async def _call(fn, *a):
            out = fn(*a)
            return await out if inspect.isawaitable(out) else out

        c = dict(ctx or {})
        s = json.loads(json.dumps(c.get("store", {})))
        # 0 — the roster gate
        if not s.get("departments") or not s.get("agents"):
            if self.first_boot:
                await _call(self.first_boot, s)
                s["events"].append({"process": "workday", "observation": {
                    "status": "first_boot", "desc": "roster registered"}})
            c["store"] = s
            return LinkResult(status=LinkStatus.SUCCESS, context=c)
        # 2 — review supposedly_done
        for task in [t for t in s["tasks"].values()
                     if t["status"] == "supposedly_done"]:
            decision, note = await _call(self.reviewer, task, s)
            ceo_review_task(s, task["id"], decision)
            task["review"] = note
        # 3 — assign
        planned = bool(await _call(self.planner, s))
        # 6 — the round record + stop condition
        s["events"].append({"process": "workday",
                            "observation": {"status": "round_complete",
                                            "desc": f"day {s['day']}"}})
        pending = any(t["status"] in ("open", "supposedly_done")
                      for t in s["tasks"].values())
        if not planned and not pending:
            s["_stop"] = True
        c["store"] = s
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


# ── THE WORLD ────────────────────────────────────────────────────────────────
class JobWorld(Link):
    """THE World() class: the org on the real jobworld store. Departments are
    any Link (agents run AS entire worlds via a world-backed runtime); the CEO
    runs the workday round; the store is the single source of truth. Persist
    it with the game.json pattern (data.json+events.jsonl in the served
    system; the caller owns persistence here)."""

    def __init__(self, departments: Dict[str, Link], ceo: CEO,
                 rounds: int = 8, name: str = "jobworld"):
        self.name = name
        self.arena = blackboard(departments, jobworld_mutator(),
                                adjudicator=ceo, rounds=rounds,
                                state_key="store", name=f"{name}:org")

    async def execute(self, context=None, **_):
        ctx = dict(context or {})
        ctx.setdefault("store", jobworld_store())
        return await self.arena.execute(ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'JobWorld "{self.name}":\n' \
            + self.arena.describe(depth + 1)


__all__ = ["JobWorld", "CEO", "Department", "jobworld_store",
           "jobworld_mutator", "create_company", "create_department",
           "create_agent", "create_project", "create_milestone",
           "create_goal", "create_task", "ceo_review_task", "assign_task",
           "close_day", "get_open_tasks", "get_org_chart", "DOMAIN_ENUM"]
