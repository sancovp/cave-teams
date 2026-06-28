"""
adaptor.py — the CAVE adaptor: spin up a cave-team ON THE FLY and wire it to a frontend.

This is the library CAVE (or any agent) calls at runtime to:
  1. build a team from a plain spec (no hand-written deletable JSONs),
  2. wire its EventBus to listeners — the on-disk FileListener (always), a live
     gallery (HttpFrontendListener, if a gallery_url is given), and/or any extra
     `on_event` sink (e.g. a CAVE Channel → Discord),
  3. run it (autonomous TeamLeader) — or hand back a handle to drive programmatically.

cave-teams stays STANDALONE (claude -p + MiniMax + filesystem, no running CAVE needed).
"Using CAVE" = optionally pass a gallery_url / on_event so a running surface can watch
and steer it. The team appears in the gallery the instant it spawns.

    from cave_teams.adaptor import spawn_team
    spawn_team({
        "name": "outreach",
        "task": "find 3 leads and draft emails",
        "agents": [
            {"name": "leader",  "backend": "claude-p", "model": "claude-sonnet-4-6",
             "system_prompt": "You are the team leader."},
            {"name": "writer",  "backend": "minimax", "system_prompt": "You write cold emails."},
        ],
        "leader": {"model": "claude-sonnet-4-6", "max_turns": 40},
    }, gallery_url="http://localhost:8787")
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from .conversation import Conversation
from .harness import Harness
from .leader import TeamLeader

logger = logging.getLogger(__name__)


def build_team(
    spec: Dict[str, Any],
    gallery_url: Optional[str] = None,
    on_event: Optional[Callable] = None,
    base_dir: str = "/tmp/cave-teams",
) -> Harness:
    """Build a team from a spec and wire its event bus. Does NOT run a leader.

    Returns the Harness — register/deliver/send_message are all available, and
    every boundary already streams to the wired listeners. Use this for
    programmatic flows (you drive harness.deliver / send_message yourself).
    """
    name = spec["name"]
    team_dir = spec.get("team_dir") or f"{base_dir}/{name}"

    harness = Harness(team_dir, on_event=on_event, concurrent=spec.get("concurrent", True))
    if gallery_url:
        from .frontend import HttpFrontendListener
        harness.bus.subscribe(HttpFrontendListener(gallery_url))

    agents: List[dict] = spec.get("agents", [])
    harness.bus.emit(
        "team_spawned",
        agents=[a["name"] for a in agents],
        task=spec.get("task", ""),
    )

    for a in agents:
        conv = Conversation(
            name=a["name"],
            system_prompt=a.get("system_prompt", ""),
            backend=a.get("backend", "minimax"),
            model=a.get("model"),
            cwd=a.get("cwd", "/tmp"),
            mcp_config=a.get("mcp_config"),
        )
        harness.register(a["name"], conv)

    return harness


def spawn_team(
    spec: Dict[str, Any],
    gallery_url: Optional[str] = None,
    on_event: Optional[Callable] = None,
    run: bool = True,
    base_dir: str = "/tmp/cave-teams",
) -> Dict[str, Any]:
    """Spin up a team on the fly and (by default) run it with an autonomous leader.

    The leader is a Claude Code (`claude -p`) agent that reads/writes the JSONL
    inboxes via its tools and dispatches the workers; the Harness delivers and the
    bus streams every dispatch/response live to the gallery. Emits done/blocked/error
    at the end. If `run` is False or no task is given, returns a ready handle instead.
    """
    harness = build_team(spec, gallery_url=gallery_url, on_event=on_event, base_dir=base_dir)

    task = spec.get("task")
    if not run or not task:
        return {"team": harness.team, "harness": harness, "status": "ready"}

    leader_cfg = spec.get("leader") or {}
    leader = TeamLeader(
        harness=harness,
        task=task,
        leader_backend=leader_cfg.get("backend", "claude-p"),
        model=leader_cfg.get("model", "claude-sonnet-4-6"),
        max_turns=leader_cfg.get("max_turns", 50),
        cwd=leader_cfg.get("cwd", "."),
    )

    result = leader.run()
    status = result.get("status")
    if status in ("done", "completed"):
        harness.bus.emit("done", summary=(result.get("summary") or result.get("text", ""))[:600])
    elif status == "blocked":
        harness.bus.emit("blocked", reason=result.get("reason", ""))
    else:
        harness.bus.emit("error", error=result.get("error", "unknown"))

    return {"team": harness.team, "harness": harness, "result": result, "status": status}
