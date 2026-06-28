"""
server.py — the ephemeral cave-server factory (rule 02). THE cave-coupled module.

A cave-team spins up a NEW headless CAVEHTTPServer for itself, runs the team, tears it down.

HEADLESS construction: build a CAVEAgent with only what a team needs — agent registry + SSE +
routing + server — skipping the Sanctuary/heart/world/tmux machinery, by calling cave's OWN init
methods selectively (via __new__). cave stays untouched; this is adaptation, not reimplementation.

Agents are cave's (CaveAgentEntry -> cave Agent classes). Each gets a runtime via set_runtime.
In-process run: `await agent.run(content)` returns -> we KNOW it's done -> we write the response
file into the team dir. No hooks (those only bridge a detached/tmux runtime).

Everything cave is imported lazily inside the functions, so importing cave_teams stays host-safe.
"""
from __future__ import annotations

import asyncio
import json
import queue
import socket
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .runner import run_team, file_leader


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def make_headless_cave(config):
    """Construct a CAVEAgent with ONLY the team-server parts (no Sanctuary/heart/world/tmux).

    Calls cave's own init methods selectively via __new__ — cave's code is untouched.
    """
    from cave import CAVEAgent
    ca = CAVEAgent.__new__(CAVEAgent)
    ca.config = config
    # === state ===
    ca.paia_states = {}
    ca.agent_registry = {}
    ca.remote_agents = {}
    # === SSE (must precede cave_agents — auto-SSE needs the event queue) ===
    ca._init_sse()
    # === the agent registry — the team members ===
    ca.cave_agents = {}
    ca.central_channels = {}
    ca._init_cave_agents()
    # === dirs ===
    config.data_dir.mkdir(parents=True, exist_ok=True)
    config.hook_dir.mkdir(parents=True, exist_ok=True)
    return ca


class EphemeralTeamServer:
    """A non-blocking CAVEHTTPServer for one team, with clean teardown."""

    def __init__(self, cave_agent, port: Optional[int] = None, host: str = "127.0.0.1"):
        from cave.server.cave_http_server import CAVEHTTPServer
        self.cave = cave_agent
        self.host = host
        self.port = port or _free_port()
        self.http = CAVEHTTPServer(cave_agent, port=self.port, host=host)
        self.events = queue.Queue()          # team-event stream for the live dashboard
        self._server = None
        self._thread = None
        self._add_team_routes()

    def emit(self, ev: dict) -> None:
        """Push a team event onto the live stream (thread-safe; the SSE generator drains it)."""
        self.events.put(ev)

    def _add_team_routes(self) -> None:
        """Add /team (the gallery) + /team/events (the team-event SSE) — cave-teams owns the
        team-event stream (only team events, not cave's full LLM firehose)."""
        from starlette.responses import HTMLResponse, StreamingResponse
        gallery_html = (Path(__file__).parent / "gallery.html").read_text()
        app, q = self.http.app, self.events

        @app.get("/team")
        def _gallery():
            return HTMLResponse(gallery_html)

        @app.get("/team/events")
        async def _team_events():
            async def gen():
                while True:
                    try:
                        yield "data: " + json.dumps(q.get_nowait()) + "\n\n"
                    except queue.Empty:
                        await asyncio.sleep(0.15)
            return StreamingResponse(gen(), media_type="text/event-stream")

    def start(self) -> "EphemeralTeamServer":
        import uvicorn
        cfg = uvicorn.Config(self.http.app, host=self.host, port=self.port, log_level="warning")
        self._server = uvicorn.Server(cfg)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)


def _run_agent_inprocess(agent, content: str) -> str:
    """Run a cave agent on `content` in-process and return its output string.
    'we just know when they return' — await agent.run delegates to the DI'd runtime."""
    out = asyncio.run(agent.run(content))
    return out if isinstance(out, str) else ("" if out is None else str(out))


def cave_team(
    team,
    agent_runtimes: Dict[str, Any],
    leader_runtime: Any,
    task: str,
    leader_name: str = "leader",
    open_rules: Optional[Dict[str, List[str]]] = None,
    team_dir: Optional[str] = None,
    base_dir: str = "/tmp/cave_teams",
    serve: bool = True,
    port: Optional[int] = None,
    max_steps: int = 30,
    linger: float = 0,
) -> Dict[str, Any]:
    """Make an ephemeral cave server for `team` and run it LEADER-DRIVEN, then tear it down.

    The leader (`leader_runtime`) and teammates (`agent_runtimes`) are CAVE agents (`set_runtime`
    backends). cave-teams stands up a headless CAVEHTTPServer hosting them, then `run_team` drives the
    leader: it WRITES message files into the session's leader_outbox, cave-teams CHECKS each against
    the guardrail (+ re-prompts on {e}), valid ones are delivered to teammate inboxes and run, the
    leader is alerted, until it ENDS with a report. The server is torn down at the end.

    leader_runtime needs file tools (e.g. MiniMaxRuntime(tools=None)); teammates can be tool-less
    (they return text, which cave-teams logs as their response).
    """
    from cave.core.config import CAVEConfig
    from cave.core.models import CaveAgentEntry

    if isinstance(team, str):
        raise TypeError("pass a Team INSTANCE (it carries agents); got a team name")

    teammate_names = sorted({e.to for e in team.edges()})
    all_names = [leader_name] + [n for n in teammate_names if n != leader_name]
    tdir = team_dir or f"{base_dir}/{getattr(team, 'op', None) or 'team'}"

    config = CAVEConfig(
        agents=[CaveAgentEntry(name=n, agent_type="chat") for n in all_names],
        data_dir=Path(tdir) / "_cave_data",
        hook_dir=Path(tdir) / "_cave_hooks",
        host="127.0.0.1",
        port=port or _free_port(),
    )
    cave = make_headless_cave(config)

    cave.cave_agents[leader_name].set_runtime(leader_runtime)
    for n in teammate_names:
        if n in agent_runtimes:
            cave.cave_agents[n].set_runtime(agent_runtimes[n])

    server = EphemeralTeamServer(cave, port=config.port).start() if serve else None
    leader_agent = cave.cave_agents[leader_name]
    teammates = {n: cave.cave_agents[n] for n in teammate_names}
    on_event = server.emit if server is not None else None
    if server is not None:
        server.emit({"kind": "team", "data": {"leader": leader_name, "members": teammate_names, "task": task}})

    try:
        res = run_team(team, task, file_leader(leader_agent), teammates, tdir,
                       open_rules=open_rules, on_event=on_event, max_steps=max_steps)
    finally:
        if server is not None:
            if linger > 0:
                import time as _t
                _t.sleep(linger)          # keep the dashboard up after the run for inspection
            server.stop()

    res["team_dir"] = tdir
    res["dashboard"] = f"http://{server.host}:{server.port}/team?live" if server else None
    return res
