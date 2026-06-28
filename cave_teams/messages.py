"""
messages.py — the team message substrate (THE MAIN THING, rule 01).

A message IS a file in the team's messages dir. The team event/message format carries
who -> who. cave-teams CHECKs the dir continuously and LIFTs (dispatches) only when
conditions are met. Dispatch sends a POINTER ("read {path}"), never the payload — the
agent reads the file at {path} and writes its response back into the dir.

Pure stdlib: no cave, no chain-ontology, no pydantic. This is the on-disk channel that
cave (the central event system) gets adapted to watch — so it reacts to ONLY team events,
not every LLM event.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Union

# message kinds = the team events (kept small + stable so conditions switch on them)
DISPATCH = "dispatch"   # runtime/leader -> agent: a pointer, "read {path}"
RESPONSE = "response"   # agent -> team: a final response written into the dir
FLAG = "flag"           # a runtime condition flag was set
DONE = "done"           # the team finished


@dataclass
class TeamMessage:
    """One team message — the unit conditions read and a frontend renders.

    Big payloads live at `path` (pointer-not-payload, never-truncate); `text` stays small.
    """
    frm: str
    to: str
    kind: str = RESPONSE
    path: str = ""
    text: str = ""
    one_liner_to_show_user: str = ""   # the human-facing 1-line status the dashboard renders
    data: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TeamMessage":
        keys = ("frm", "to", "kind", "path", "text", "one_liner_to_show_user", "data", "id", "ts")
        return cls(**{k: d[k] for k in keys if k in d})


class TeamDir:
    """The team's on-disk channel.

    `messages/` holds one JSON file per message (the team events).
    `artifacts/` holds the payloads that pointers point at (so dispatch stays a pointer).
    """

    def __init__(self, team_dir: Union[str, Path]):
        self.root = Path(team_dir)
        self.messages = self.root / "messages"
        self.artifacts = self.root / "artifacts"
        self.messages.mkdir(parents=True, exist_ok=True)
        self.artifacts.mkdir(parents=True, exist_ok=True)

    # ---- messages (the team events) ----
    def write(self, msg: TeamMessage) -> Path:
        p = self.messages / f"{msg.ts:.6f}-{msg.frm}-{msg.id}.json"
        p.write_text(json.dumps(msg.to_dict(), indent=2))
        return p

    def read_all(self) -> List[TeamMessage]:
        out: List[TeamMessage] = []
        for p in sorted(self.messages.glob("*.json")):
            try:
                out.append(TeamMessage.from_dict(json.loads(p.read_text())))
            except Exception:
                continue
        return sorted(out, key=lambda m: m.ts)

    # ---- artifacts (the payloads pointers reference) ----
    def write_artifact(self, name: str, content: str) -> str:
        p = self.artifacts / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return str(p)

    def read_artifact(self, path: Union[str, Path]) -> str:
        return Path(path).read_text()
