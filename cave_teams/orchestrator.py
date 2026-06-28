"""
Team orchestrator — create teams, add agents, dispatch cycles.

A Team is a directory with:
  /tasks/         ← shared task list (JSONL)
  /transcripts/   ← per-agent transcript JSONL
  /state/         ← per-agent state files {"doing": "x", "phase": "y"}
  /messages/      ← inter-agent message queue
  /config.json    ← team definition (agents, settings)
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional
from enum import Enum

from .primitives import run_opus, run_minimax, continue_opus, AgentResult

logger = logging.getLogger(__name__)


class AgentBackend(str, Enum):
    OPUS = "opus"
    MINIMAX = "minimax"


@dataclass
class TeamAgent:
    """Agent definition within a team."""
    name: str
    system_prompt: str
    backend: AgentBackend = AgentBackend.MINIMAX
    model: Optional[str] = None
    mcp_config: Optional[str] = None
    session_id: Optional[str] = None
    state: str = "idle"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "backend": self.backend.value,
            "model": self.model,
            "state": self.state,
            "session_id": self.session_id,
        }


@dataclass
class Task:
    """A task in the shared task list."""
    id: str
    subject: str
    description: str = ""
    status: str = "pending"
    owner: Optional[str] = None
    blocked_by: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "subject": self.subject,
            "description": self.description,
            "status": self.status,
            "owner": self.owner,
            "blocked_by": self.blocked_by,
            "created_at": self.created_at,
        }


class Team:
    """Programmable agent team.

    Usage:
        team = Team("metacog", base_dir="/tmp/cave-teams")
        team.add_agent(TeamAgent(name="executor", system_prompt="...", backend=AgentBackend.OPUS))
        team.add_agent(TeamAgent(name="observer", system_prompt="...", backend=AgentBackend.MINIMAX))
        team.create_task(Task(id="1", subject="Build feature X"))
        result = team.run_agent("executor", "Do task #1")
    """

    def __init__(self, name: str, base_dir: str = "/tmp/cave-teams"):
        self.name = name
        self.dir = Path(base_dir) / name
        self.agents: Dict[str, TeamAgent] = {}
        self.tasks: List[Task] = []
        self._ensure_dirs()
        self._load_config()

    def _ensure_dirs(self):
        for subdir in ["tasks", "transcripts", "state", "messages"]:
            (self.dir / subdir).mkdir(parents=True, exist_ok=True)

    def _load_config(self):
        config_path = self.dir / "config.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            for agent_data in data.get("agents", []):
                agent = TeamAgent(
                    name=agent_data["name"],
                    system_prompt=agent_data.get("system_prompt", ""),
                    backend=AgentBackend(agent_data.get("backend", "minimax")),
                    model=agent_data.get("model"),
                    session_id=agent_data.get("session_id"),
                )
                self.agents[agent.name] = agent

    def _save_config(self):
        config_path = self.dir / "config.json"
        data = {
            "name": self.name,
            "agents": [a.to_dict() for a in self.agents.values()],
            "created_at": time.time(),
        }
        config_path.write_text(json.dumps(data, indent=2))

    def add_agent(self, agent: TeamAgent):
        self.agents[agent.name] = agent
        self._save_config()
        logger.info("Added agent %s (backend=%s) to team %s", agent.name, agent.backend.value, self.name)

    def run_agent(self, agent_name: str, prompt: str, cwd: str = ".") -> AgentResult:
        """Run an agent with a prompt. Routes to correct backend."""
        agent = self.agents.get(agent_name)
        if not agent:
            return AgentResult(error=f"Agent '{agent_name}' not found", success=False)

        self._set_state(agent_name, "running")
        transcript_dir = str(self.dir / "transcripts" / agent_name)

        if agent.backend == AgentBackend.OPUS:
            if agent.session_id:
                result = continue_opus(agent.session_id, prompt, cwd=cwd, transcript_dir=transcript_dir)
            else:
                result = run_opus(agent.system_prompt, prompt, cwd=cwd,
                                  mcp_config=agent.mcp_config, transcript_dir=transcript_dir)
                if result.session_id:
                    agent.session_id = result.session_id
                    self._save_config()
        else:
            result = run_minimax(agent.system_prompt, prompt,
                                 model=agent.model or "MiniMax-M2.7-highspeed")

        self._set_state(agent_name, "idle")
        self._write_transcript(agent_name, prompt, result)
        return result

    def _set_state(self, agent_name: str, state: str):
        state_path = self.dir / "state" / f"{agent_name}.json"
        state_path.write_text(json.dumps({
            "agent": agent_name,
            "state": state,
            "timestamp": time.time(),
        }))

    def _write_transcript(self, agent_name: str, prompt: str, result: AgentResult):
        transcript_path = self.dir / "transcripts" / f"{agent_name}.jsonl"
        entry = {
            "ts": time.time(),
            "prompt": prompt[:500],
            "output": result.text[:2000],
            "duration_ms": result.duration_ms,
            "success": result.success,
            "error": result.error,
        }
        with open(transcript_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def send_message(self, from_agent: str, to_agent: str, content: str):
        """Send a message between agents (file-based)."""
        msg_path = self.dir / "messages" / f"{to_agent}.jsonl"
        msg = {
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "ts": time.time(),
        }
        with open(msg_path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        logger.info("Message %s → %s", from_agent, to_agent)

    def get_messages(self, agent_name: str) -> List[dict]:
        """Get pending messages for an agent."""
        msg_path = self.dir / "messages" / f"{agent_name}.jsonl"
        if not msg_path.exists():
            return []
        messages = []
        for line in msg_path.read_text().splitlines():
            if line.strip():
                messages.append(json.loads(line))
        # Clear after reading
        msg_path.write_text("")
        return messages

    def create_task(self, task: Task):
        self.tasks.append(task)
        self._save_tasks()

    def get_next_task(self) -> Optional[Task]:
        """Get next unblocked pending task."""
        for task in self.tasks:
            if task.status == "pending" and not task.blocked_by:
                return task
            if task.blocked_by:
                # Check if blockers are done
                all_done = all(
                    any(t.id == bid and t.status == "completed" for t in self.tasks)
                    for bid in task.blocked_by
                )
                if all_done:
                    task.blocked_by = []
                    return task
        return None

    def complete_task(self, task_id: str):
        for task in self.tasks:
            if task.id == task_id:
                task.status = "completed"
        self._save_tasks()

    def _save_tasks(self):
        tasks_path = self.dir / "tasks" / "tasks.json"
        tasks_path.write_text(json.dumps([t.to_dict() for t in self.tasks], indent=2))

    def get_all_states(self) -> Dict[str, dict]:
        """Get current state of all agents (for dashboard)."""
        states = {}
        for agent_name in self.agents:
            state_path = self.dir / "state" / f"{agent_name}.json"
            if state_path.exists():
                states[agent_name] = json.loads(state_path.read_text())
            else:
                states[agent_name] = {"agent": agent_name, "state": "unknown"}
        return states
