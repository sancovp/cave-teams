"""Container test: the live team-event SSE — EphemeralTeamServer.emit -> /team/events stream,
and /team serves the gallery."""
import json
import tempfile
import time
from pathlib import Path

import httpx

from cave_teams.server import make_headless_cave, EphemeralTeamServer


def _cfg():
    from cave.core.config import CAVEConfig
    from cave.core.models import CaveAgentEntry
    base = Path(tempfile.mkdtemp())
    return CAVEConfig(agents=[CaveAgentEntry(name="leader", agent_type="chat")],
                      data_dir=base / "d", hook_dir=base / "h", host="127.0.0.1", port=0)


def main():
    cave = make_headless_cave(_cfg())
    srv = EphemeralTeamServer(cave).start()
    time.sleep(0.7)                                   # let uvicorn bind
    base = f"http://127.0.0.1:{srv.port}"

    r = httpx.get(base + "/team", timeout=5)
    assert r.status_code == 200 and 'id="graph"' in r.text, ("gallery route", r.status_code)
    print("ok  /team serves the gallery (graph present)")

    evs = [
        {"kind": "team", "data": {"leader": "leader", "members": ["researcher", "writer"], "task": "demo"}},
        {"kind": "dispatch", "data": {"to": "researcher", "prompt": "go", "one_liner_to_show_user": "researching"}},
        {"kind": "response", "data": {"frm": "researcher", "text": "done", "one_liner_to_show_user": "found facts"}},
    ]
    for e in evs:
        srv.emit(e)

    got = []
    with httpx.stream("GET", base + "/team/events", timeout=5) as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                got.append(json.loads(line[5:].strip()))
                if len(got) >= 3:
                    break
    srv.stop()

    kinds = [g["kind"] for g in got]
    assert kinds == ["team", "dispatch", "response"], kinds
    assert got[1]["data"]["one_liner_to_show_user"] == "researching"
    print("ok  /team/events streamed the team events:", kinds)
    print("\nLIVE SSE TEST PASSED")


if __name__ == "__main__":
    main()
