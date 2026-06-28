"""
events.py — the on_event SEAM for cave-teams.

This is the piece the original 2026-05-18 build never wrote: a decoupled
event stream OUT. Every team boundary (agent added, dispatched, responded,
message, task update, done, blocked, error) emits a TeamEvent through an
EventBus. Listeners subscribe; the bus fans out. A FRONTEND is just a listener:
files, a web/SSE gallery, Discord, a CAVE Channel — all interchangeable.

Control IN (send_message → an agent's inbox) already existed in the Harness;
this adds the missing events-OUT half so a team can be watched + projected
on the fly without polling files.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List

EventListener = Callable[["TeamEvent"], None]

# The boundary kinds a team emits. Kept small + stable so frontends can switch on them.
KINDS = (
    "team_spawned",   # a team was created (data: agents=[...], task=...)
    "agent_added",    # an agent joined the team (data: backend, model)
    "dispatched",     # a message was handed to an agent to process (data: frm, content)
    "stream",         # a live token delta from an agent's in-progress turn (data: delta)
    "response",       # an agent finished a turn (data: to, text, duration_ms)
    "message",        # a message was queued to an agent's inbox (data: frm, content)
    "task",           # a task changed state (data: id, status, ...)
    "flag",           # a runtime condition flag was set (data: flag, value) — gates firing
    "done",           # the team finished (data: summary)
    "blocked",        # the team is blocked / needs input (data: reason)
    "error",          # an agent turn errored (data: error)
)


@dataclass
class TeamEvent:
    """One thing that happened in a team. The unit a frontend renders."""
    team: str
    kind: str
    agent: str = ""                       # which agent (alias) this is about, if any
    data: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "team": self.team,
            "kind": self.kind,
            "agent": self.agent,
            "data": self.data,
            "ts": self.ts,
        }


class EventBus:
    """Fan-out of TeamEvents to registered listeners.

    A listener that raises is swallowed — a frontend can NEVER kill a run
    (same discipline as promptworld's guarded on_event callback).
    """

    def __init__(self, team: str):
        self.team = team
        self._listeners: List[EventListener] = []
        self._lock = threading.Lock()

    def subscribe(self, listener: EventListener) -> EventListener:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)
        return listener

    def unsubscribe(self, listener: EventListener) -> None:
        with self._lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def emit(self, kind: str, agent: str = "", **data) -> TeamEvent:
        ev = TeamEvent(team=self.team, kind=kind, agent=agent, data=data)
        for listener in list(self._listeners):
            try:
                listener(ev)
            except Exception:
                pass
        return ev


class FileListener:
    """Default listener — preserves cave-teams' original on-disk behavior.

    Appends every event to <team_dir>/events.jsonl. This makes "watch by
    polling files" still work, but now as ONE listener among many rather than
    the only hardcoded option.
    """

    def __init__(self, team_dir: str):
        self.dir = Path(team_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.dir / "events.jsonl"
        self._lock = threading.Lock()  # concurrent agents emit from many threads

    def __call__(self, ev: TeamEvent) -> None:
        if ev.kind == "stream":
            return  # ephemeral token deltas are not persisted (the 'response' event has full text)
        with self._lock:
            with open(self.events_path, "a") as f:
                f.write(json.dumps(ev.to_dict()) + "\n")


class CallbackListener:
    """Adapts a plain `def cb(dict)` into an event listener (dict form)."""

    def __init__(self, cb: Callable[[dict], None]):
        self._cb = cb

    def __call__(self, ev: TeamEvent) -> None:
        self._cb(ev.to_dict())
