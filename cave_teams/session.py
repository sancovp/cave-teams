"""
session.py — the per-team SESSION dir structure (Isaac's spec: team → sessions → session → inbox).

    <team_dir>/sessions/<session_id>/
        task.txt              # the task file the leader is told to check
        leader_outbox/        # the leader WRITES its message file here; cave-teams reads + checks it
        inbox/<teammate>/     # delivered (post-guardrail) messages — what each teammate reads
        messages/             # the flat team-event LOG (every dispatch + response) — conditions read this
        artifacts/            # the payloads that message pointers reference

The guardrail gate sits between leader_outbox (proposed) and inbox/<teammate> (delivered): a message
is only copied into a teammate's inbox once it passes the check.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Union

from .messages import TeamMessage


class TeamSession:
    def __init__(self, team_dir: Union[str, Path], session_id: str = "session"):
        self.root = Path(team_dir) / "sessions" / session_id
        self.outbox = self.root / "leader_outbox"
        self.inbox = self.root / "inbox"
        self.messages = self.root / "messages"
        self.artifacts = self.root / "artifacts"
        for d in (self.outbox, self.inbox, self.messages, self.artifacts):
            d.mkdir(parents=True, exist_ok=True)

    # ── task ──
    def write_task(self, task: str) -> str:
        p = self.root / "task.txt"
        p.write_text(task)
        return str(p)

    # ── the leader's outbox (it writes its proposed message file here) ──
    def outbox_path(self, n: int) -> str:
        return str(self.outbox / f"msg_{n:03d}.json")

    # ── the flat team-event log (what conditions read) ──
    def log(self, msg: TeamMessage) -> Path:
        p = self.messages / f"{msg.ts:.6f}-{msg.frm}-{msg.id}.json"
        p.write_text(json.dumps(msg.to_dict(), indent=2))
        return p

    def read_log(self) -> List[TeamMessage]:
        out: List[TeamMessage] = []
        for p in sorted(self.messages.glob("*.json")):
            try:
                out.append(TeamMessage.from_dict(json.loads(p.read_text())))
            except Exception:
                continue
        return sorted(out, key=lambda m: m.ts)

    # ── delivery to a teammate's inbox (post-guardrail) + log ──
    def deliver(self, msg: TeamMessage) -> str:
        box = self.inbox / msg.to
        box.mkdir(parents=True, exist_ok=True)
        p = box / f"{msg.ts:.6f}-{msg.id}.json"
        p.write_text(json.dumps(msg.to_dict(), indent=2))
        self.log(msg)
        return str(p)

    # ── artifacts (payloads pointers reference) ──
    def write_artifact(self, name: str, content: str) -> str:
        p = self.artifacts / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return str(p)

    def read_artifact(self, path: Union[str, Path]) -> str:
        return Path(path).read_text()
