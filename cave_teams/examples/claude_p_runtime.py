"""claude_p_runtime.py — a claude -p `set_runtime` backend (the other example instance).

A PLAIN runtime, NOT a Link: cave's `set_runtime` takes any object with `.run(str) -> str`.
Mirrors the pre-rebuild `primitives.run_opus`/`continue_opus` (the proven claude -p path): first
turn spawns `claude -p --output-format stream-json`, later turns resume via `-r <session_id>` so the
agent keeps one conversation. ANTHROPIC_API_KEY is stripped from the subprocess env so claude -p
uses subscription auth.

Exposes `transcript_path` / `conversation_id` after each run so the leader's finish-alert
(runner._run_teammate meta extraction) can carry them.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import List, Optional

DEFAULT_MODEL = "claude-sonnet-4-6"


def _claude_env() -> dict:
    """Subprocess env with ANTHROPIC_API_KEY stripped so claude -p uses subscription auth."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def _parse_claude_stream(stdout: str, transcript_dir: Optional[str] = None) -> dict:
    """Parse claude -p stream-json output. Returns {text, session_id, transcript_path}."""
    text_parts: List[str] = []
    session_id = None
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            text_parts.append(line)
            continue
        events.append(event)
        etype = event.get("type", "")
        if etype == "system" and event.get("subtype") == "init":
            session_id = event.get("session_id") or session_id
        elif etype == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    text_parts.append(block["text"])
        elif etype == "result" and event.get("is_error"):
            text_parts.append(event.get("result", ""))

    transcript_path = None
    if transcript_dir:
        Path(transcript_dir).mkdir(parents=True, exist_ok=True)
        transcript_path = str(Path(transcript_dir) / f"{int(time.time())}.jsonl")
        with open(transcript_path, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")
    return {"text": "".join(text_parts), "session_id": session_id, "transcript_path": transcript_path}


class ClaudePRuntime:
    """A claude -p agent backend for cave's `set_runtime`. `.run(prompt) -> str`.

    Holds a `session_id` so repeated turns continue one conversation (per-agent memory).
    """

    def __init__(self, name: str = "agent", system_prompt: str = "", model: Optional[str] = None,
                 cwd: str = ".", mcp_config: Optional[str] = None, max_turns: int = 50,
                 transcript_dir: Optional[str] = None, timeout: int = 600):
        self.name = name
        self.system_prompt = system_prompt
        self.model = model or os.environ.get("CAVE_CLAUDE_MODEL") or DEFAULT_MODEL
        self.cwd = cwd
        self.mcp_config = mcp_config
        self.max_turns = max_turns
        self.transcript_dir = transcript_dir
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self.transcript_path: Optional[str] = None

    @property
    def conversation_id(self) -> Optional[str]:
        return self.session_id

    def run(self, prompt: str) -> str:
        if self.session_id:
            cmd = ["claude", "-p", "-r", self.session_id,
                   "--model", self.model,
                   "--permission-mode", "bypassPermissions",
                   "--output-format", "stream-json"]
        else:
            cmd = ["claude", "-p",
                   "--model", self.model,
                   "--system-prompt", self.system_prompt,
                   "--permission-mode", "bypassPermissions",
                   "--output-format", "stream-json",
                   "--max-turns", str(self.max_turns)]
            if self.mcp_config:
                cmd += ["--mcp-config", self.mcp_config]

        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              cwd=self.cwd, timeout=self.timeout, env=_claude_env())
        parsed = _parse_claude_stream(proc.stdout, self.transcript_dir)
        self.session_id = parsed["session_id"] or self.session_id
        self.transcript_path = parsed["transcript_path"] or self.transcript_path
        return parsed["text"]

    def reset(self) -> None:
        """Drop the session — start a fresh conversation."""
        self.session_id = None
