"""
Team Leader — a Claude Code agent (claude -p or tmux) that orchestrates via file-based messaging.

The leader reads and writes JSONL message files. The Harness watches those files
and delivers messages to MiniMax/Opus worker agents. Responses appear in the
leader's own JSONL file.

Two backends:
  - claude-p: subprocess with --max-turns, self-contained (implemented)
  - tmux: persistent session, CAVE server injects prompts (stubbed)
"""

import json
import logging
import time
from pathlib import Path
from typing import Dict, Optional

from .primitives import run_opus, AgentResult
from .harness import Harness

logger = logging.getLogger(__name__)

LEADER_SYSTEM_PROMPT = """You are the TEAM LEADER running inside Claude Code. You orchestrate worker agents by writing and reading message files.

## Your Agents
{agent_list}

## Message Directory
{msg_dir}

## How To Dispatch An Agent
Write a JSON line to their message file:
```bash
echo '{{"from":"leader","content":"YOUR INSTRUCTIONS HERE","ts":'$(date +%s)'.0}}' >> {msg_dir}/AGENT_NAME.jsonl
```
The system watches these files and delivers your message to the agent automatically.

## How To Read Responses
Responses appear in YOUR message file:
```bash
cat {msg_dir}/leader.jsonl
```
Or read the latest response:
```bash
tail -1 {msg_dir}/leader.jsonl
```

## How To Check Agent Status
```bash
cat {state_dir}/AGENT_NAME.json
```
States: idle, processing

## Your Job
1. Read the task below
2. Dispatch agents by writing to their JSONL files
3. Wait a moment for the agent to process (check their state file)
4. Read responses from your own JSONL file
5. Decide what to do next
6. Repeat until done

You have FULL Claude Code capabilities — WebSearch, Bash, Read, Write, computer-use. Use them freely for research, analysis, or any work the agents can't do.

## When Done
Write a file called DONE.txt with a summary:
```bash
echo "SUMMARY: your summary here" > {team_dir}/DONE.txt
```

## When Blocked
Write a file called BLOCKED.txt with the reason:
```bash
echo "REASON: why you are blocked" > {team_dir}/BLOCKED.txt
```
"""


def _claude_p_env():
    """Env for claude -p subprocess — strip ANTHROPIC_API_KEY for subscription auth."""
    import os
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


class TeamLeader:
    """Leader agent that orchestrates via file-based messaging.

    Usage:
        harness = Harness("/tmp/cave-teams/my-team")
        harness.register("worker1", Conversation(...))

        leader = TeamLeader(harness, task="Do the thing")
        result = leader.run()  # Runs until DONE or BLOCKED
    """

    def __init__(self, harness: Harness, task: str,
                 leader_backend: str = "claude-p",
                 model: str = "claude-sonnet-4-6",
                 max_turns: int = 50,
                 cwd: str = "."):
        self.harness = harness
        self.task = task
        self.leader_backend = leader_backend
        self.model = model
        self.max_turns = max_turns
        self.cwd = cwd

        agent_list = "\n".join(
            f"- {name} ({conv.backend}) — write to {harness.msg_dir}/{name}.jsonl"
            for name, conv in harness.agents.items()
        )
        self.system_prompt = LEADER_SYSTEM_PROMPT.format(
            agent_list=agent_list,
            msg_dir=str(harness.msg_dir),
            state_dir=str(harness.state_dir),
            team_dir=str(harness.team_dir),
        )

    def run(self) -> dict:
        if self.leader_backend == "claude-p":
            return self._run_claude_p()
        elif self.leader_backend == "tmux":
            return self._run_tmux()
        else:
            return {"status": "error", "error": f"Unknown backend: {self.leader_backend}"}

    def _run_claude_p(self) -> dict:
        """Run leader as claude -p subprocess. Harness runs in background."""
        watcher = self.harness.start(blocking=False)

        print(f"[LEADER] claude -p | model={self.model} | max_turns={self.max_turns}")
        print(f"[LEADER] Task: {self.task}")
        print(f"[LEADER] Agents: {list(self.harness.agents.keys())}")
        print(f"[LEADER] Messages: {self.harness.msg_dir}")

        result = run_opus(
            system_prompt=self.system_prompt,
            prompt=self.task,
            cwd=self.cwd,
            model=self.model,
            max_turns=self.max_turns,
        )

        self.harness.stop()

        done_file = self.harness.team_dir / "DONE.txt"
        blocked_file = self.harness.team_dir / "BLOCKED.txt"

        if done_file.exists():
            summary = done_file.read_text().strip()
            return {"status": "done", "summary": summary,
                    "duration_ms": result.duration_ms, "text": result.text}
        elif blocked_file.exists():
            reason = blocked_file.read_text().strip()
            return {"status": "blocked", "reason": reason,
                    "duration_ms": result.duration_ms, "text": result.text}
        elif result.success:
            return {"status": "completed", "duration_ms": result.duration_ms,
                    "text": result.text}
        else:
            return {"status": "error", "error": result.error,
                    "duration_ms": result.duration_ms}

    def _run_tmux(self) -> dict:
        """Run leader as persistent tmux Claude Code session. CAVE server injects prompts."""
        raise NotImplementedError(
            "tmux backend not yet implemented. "
            "For tmux-based leader: CAVE server manages the tmux session, "
            "sends prompts via send_keys, reads output via capture-pane. "
            "The leader calls the CAVE HTTP API to start/manage the team."
        )
