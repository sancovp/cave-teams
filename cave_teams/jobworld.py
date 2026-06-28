"""
JobworldTeam — Jobworld company built on cave-teams.

CEO is a TeamLeader. Department agents are Conversations.
Data model matches twi-jobworld (company, departments, agents, tasks, events, SOPs).
Agent .md definitions become system_prompt for Conversations.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .conversation import Conversation
from .harness import Harness
from .leader import TeamLeader

logger = logging.getLogger(__name__)

DOMAIN_ENUM = [
    "ops", "sales", "marketing", "engineering", "finance",
    "hr", "legal", "admin", "research", "content",
    "growth", "support", "bi", "product",
]

EVENT_SKILL_PROMPT = """
When you complete a task, report your result in this EXACT format on its own line:

EVENT: {"goal_id": "<goal>", "dept": "<your_dept>", "task": "<task_id>", "status": "completed", "desc": "<what you did>", "process": "<process_name>", "kv": {}}

When blocked:

EVENT: {"goal_id": "<goal>", "dept": "<your_dept>", "task": "<task_id>", "status": "blocked", "desc": "<why blocked>", "process": "<process_name>", "kv": {}}

Always include the EVENT line so the CEO can track your work.
"""


_id_counter = 0

def _next_id(prefix: str) -> str:
    global _id_counter
    _id_counter += 1
    return f"{prefix}-{int(time.time() * 1000)}-{_id_counter}"


class JobworldTeam:
    """Jobworld company on cave-teams. CEO orchestrates department agents."""

    def __init__(self, name: str, base_dir: str = "/tmp/cave-teams"):
        self.name = name
        self.base_dir = Path(base_dir)
        self.team_dir = self.base_dir / name

        self.store: Dict[str, Any] = {
            "company": None,
            "departments": {},
            "agents": {},
            "projects": {},
            "milestones": {},
            "goals": {},
            "tasks": {},
            "events": [],
            "sop_patterns": {},
            "day": 1,
            "day_started_at": datetime.now().isoformat(),
        }

        self.harness = Harness(str(self.team_dir))
        self._data_path = self.team_dir / "data.json"
        self._events_path = self.team_dir / "events.jsonl"
        self._load_data()

    # ========================================
    # COMPANY SETUP
    # ========================================

    def create_company(self, description: str = "", fresh: bool = True) -> dict:
        if fresh:
            self.store = {
                "company": None, "departments": {}, "agents": {},
                "projects": {}, "milestones": {}, "goals": {},
                "tasks": {}, "events": [], "sop_patterns": {},
                "day": 1, "day_started_at": datetime.now().isoformat(),
            }
            self.harness.agents.clear()
            for d in [self.harness.msg_dir, self.harness.state_dir, self.harness.transcript_dir]:
                if d.exists():
                    for f in d.iterdir():
                        f.unlink()
            for f in [self.team_dir / "DONE.txt", self.team_dir / "BLOCKED.txt"]:
                if f.exists():
                    f.unlink()
        company = {
            "id": _next_id("company"),
            "name": self.name,
            "description": description,
            "dept_ids": [],
            "created_at": datetime.now().isoformat(),
        }
        self.store["company"] = company
        self._save_data()
        return company

    def add_department(self, name: str, agent_prompt: str,
                       backend: str = "minimax",
                       model: Optional[str] = None,
                       cwd: str = "/tmp",
                       agent_names: Optional[List[str]] = None) -> dict:
        dept_id = _next_id("dept")
        dept = {
            "id": dept_id,
            "name": name,
            "agents": [],
            "created_at": datetime.now().isoformat(),
        }
        self.store["departments"][dept_id] = dept

        if self.store["company"]:
            self.store["company"]["dept_ids"].append(dept_id)

        if not agent_names:
            agent_names = [f"{name}-lead"]

        for agent_name in agent_names:
            agent_id = _next_id("agent")
            agent = {
                "id": agent_id,
                "dept_id": dept_id,
                "name": agent_name,
                "status": "idle",
                "current_task_id": None,
                "created_at": datetime.now().isoformat(),
            }
            self.store["agents"][agent_id] = agent
            dept["agents"].append(agent_id)

            full_prompt = (
                f"You are {agent_name} in the {name} department of {self.name}.\n\n"
                f"{agent_prompt}\n\n"
                f"{EVENT_SKILL_PROMPT}"
            )
            conv = Conversation(
                name=agent_name,
                system_prompt=full_prompt,
                backend=backend,
                model=model,
                cwd=cwd,
            )
            self.harness.register(agent_name, conv)
            time.sleep(0.01)

        self._save_data()
        return dept

    # ========================================
    # TASK MANAGEMENT
    # ========================================

    def create_project(self, name: str, description: str = "") -> dict:
        project = {
            "id": _next_id("project"),
            "name": name,
            "description": description,
            "milestones": [],
            "created_at": datetime.now().isoformat(),
        }
        self.store["projects"][project["id"]] = project
        self._save_data()
        return project

    def create_milestone(self, project_id: str, description: str) -> dict:
        ms = {
            "id": _next_id("milestone"),
            "project_id": project_id,
            "description": description,
            "status": "pending",
            "goals": [],
            "created_at": datetime.now().isoformat(),
        }
        self.store["milestones"][ms["id"]] = ms
        project = self.store["projects"].get(project_id)
        if project:
            project["milestones"].append(ms["id"])
        self._save_data()
        return ms

    def create_goal(self, milestone_id: str, description: str) -> dict:
        goal = {
            "id": _next_id("goal"),
            "milestone_id": milestone_id,
            "description": description,
            "status": "pending",
            "tasks": [],
            "created_at": datetime.now().isoformat(),
        }
        self.store["goals"][goal["id"]] = goal
        ms = self.store["milestones"].get(milestone_id)
        if ms:
            ms["goals"].append(goal["id"])
        self._save_data()
        return goal

    def create_task(self, goal_id: str, dept: str, description: str) -> dict:
        task = {
            "id": _next_id("task"),
            "goal_id": goal_id,
            "dept": dept,
            "agent_id": None,
            "description": description,
            "status": "open",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        self.store["tasks"][task["id"]] = task
        goal = self.store["goals"].get(goal_id)
        if goal:
            goal["tasks"].append(task["id"])
        self._save_data()
        return task

    # ========================================
    # EVENT PROCESSING
    # ========================================

    def emit_event(self, source: str, observation: dict, round_num: int = 0) -> dict:
        event = {
            "round": round_num,
            "source": source,
            "observation": observation,
            "timestamp": datetime.now().isoformat(),
            "business": self.name,
        }
        self.store["events"].append(event)
        self._append_event(event)
        self._process_observation(event)
        self._accumulate_sop_pattern(event)
        return event

    def _process_observation(self, event: dict):
        obs = event.get("observation", {}) or {}
        task_id = obs.get("task")
        status = obs.get("status")
        task = self.store["tasks"].get(task_id)
        if not task:
            return

        if status == "completed":
            task["status"] = "supposedly_done"
            task["result"] = obs.get("desc", "")
            task["updated_at"] = datetime.now().isoformat()
        elif status == "blocked":
            task["status"] = "blocked"
            task["blocked_reason"] = obs.get("desc", "")
            task["updated_at"] = datetime.now().isoformat()
        self._save_data()

    def _accumulate_sop_pattern(self, event: dict):
        obs = event.get("observation", {}) or {}
        process = obs.get("process")
        if not process:
            return
        key = process.lower().replace(" ", "_")
        if key not in self.store["sop_patterns"]:
            self.store["sop_patterns"][key] = {
                "process": process,
                "first_seen": event["timestamp"],
                "last_seen": event["timestamp"],
                "event_count": 0,
                "steps": [],
            }
        pattern = self.store["sop_patterns"][key]
        pattern["last_seen"] = event["timestamp"]
        pattern["event_count"] += 1
        pattern["steps"].append({
            "order": pattern["event_count"],
            "agent": event.get("source", ""),
            "action": obs.get("desc", ""),
            "status": obs.get("status", ""),
            "timestamp": event["timestamp"],
        })
        self._save_data()

    def ceo_review(self, task_id: str, decision: str) -> Optional[dict]:
        task = self.store["tasks"].get(task_id)
        if not task:
            return None
        if decision == "complete":
            task["status"] = "complete"
        else:
            task["status"] = "open"
            task.pop("result", None)
        task["updated_at"] = datetime.now().isoformat()
        self._save_data()
        return task

    def parse_agent_events(self, agent_name: str, response: str, round_num: int = 0):
        for line in response.splitlines():
            line = line.strip()
            if line.startswith("EVENT:"):
                try:
                    obs = json.loads(line[6:].strip())
                    self.emit_event(agent_name, obs, round_num)
                except json.JSONDecodeError:
                    pass

    # ========================================
    # CEO LEADER
    # ========================================

    def build_ceo_prompt(self) -> str:
        open_tasks = [t for t in self.store["tasks"].values() if t["status"] == "open"]
        supposedly_done = [t for t in self.store["tasks"].values() if t["status"] == "supposedly_done"]
        recent_events = self.store["events"][-10:]

        lines = [
            f"You are CEO of {self.name}.",
            "",
            "## Departments & Agents",
        ]
        for dept in self.store["departments"].values():
            agents = [self.store["agents"][a]["name"] for a in dept["agents"] if a in self.store["agents"]]
            lines.append(f"- {dept['name']}: {', '.join(agents)}")

        if open_tasks:
            lines.append(f"\n## Open Tasks ({len(open_tasks)})")
            for t in open_tasks[:5]:
                lines.append(f"- [{t['id']}] {t['dept']}: {t['description']}")

        if supposedly_done:
            lines.append(f"\n## Pending Review ({len(supposedly_done)})")
            for t in supposedly_done[:5]:
                lines.append(f"- [{t['id']}] {t['dept']}: {t['description']} → Result: {t.get('result', '?')}")

        if recent_events:
            lines.append(f"\n## Recent Events ({len(recent_events)})")
            for e in recent_events[-5:]:
                obs = e.get("observation", {})
                lines.append(f"- {e['source']}: {obs.get('desc', '?')}")

        lines.append("\n## Your Actions")
        lines.append("DISPATCH agent-name: instructions — send work to an agent")
        lines.append("REVIEW task-id complete|reject — review a supposedly_done task")
        lines.append("DONE: summary — when all work for this round is finished")
        lines.append("BLOCKED: reason — when you need human input")

        return "\n".join(lines)

    def run_ceo(self, task: str, model: str = "claude-sonnet-4-6",
                max_turns: int = 50, cwd: str = ".") -> dict:
        ceo_context = self.build_ceo_prompt()
        full_task = f"{ceo_context}\n\n---\n\nTASK: {task}"

        leader = TeamLeader(
            harness=self.harness,
            task=full_task,
            leader_backend="claude-p",
            model=model,
            max_turns=max_turns,
            cwd=cwd,
        )
        return leader.run()

    # ========================================
    # PERSISTENCE
    # ========================================

    def _load_data(self):
        if self._data_path.exists():
            try:
                data = json.loads(self._data_path.read_text())
                for key in self.store:
                    if key in data:
                        self.store[key] = data[key]
            except Exception as e:
                logger.error("Failed to load data: %s", e)

    def _save_data(self):
        self._data_path.parent.mkdir(parents=True, exist_ok=True)
        self._data_path.write_text(json.dumps(self.store, indent=2))

    def _append_event(self, event: dict):
        self._events_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._events_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    # ========================================
    # QUERIES
    # ========================================

    def get_open_tasks(self, dept: str = None) -> list:
        tasks = [t for t in self.store["tasks"].values() if t["status"] == "open"]
        if dept:
            tasks = [t for t in tasks if t.get("dept") == dept]
        return tasks

    def get_supposedly_done(self) -> list:
        return [t for t in self.store["tasks"].values() if t["status"] == "supposedly_done"]

    def summary(self) -> dict:
        return {
            "company": self.name,
            "departments": len(self.store["departments"]),
            "agents": len(self.store["agents"]),
            "tasks_open": len(self.get_open_tasks()),
            "tasks_review": len(self.get_supposedly_done()),
            "tasks_complete": len([t for t in self.store["tasks"].values() if t["status"] == "complete"]),
            "events": len(self.store["events"]),
            "sop_patterns": len(self.store["sop_patterns"]),
            "day": self.store["day"],
        }
