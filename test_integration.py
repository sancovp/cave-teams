#!/usr/bin/env python3
"""
Integration test — the full on-the-fly path:
  start the gallery server → build a team pointed at it (gallery_url) → drive a turn
  → assert the gallery received the team's live event stream over HTTP.

Mocked agent (no API). Proves: any agent that spawns a team with gallery_url set
makes that team appear in the running gallery, live.
"""
import json
import tempfile
import threading
import time
import urllib.request

from cave_teams.frontend import TeamGalleryServer
from cave_teams import build_team, Conversation, AgentResult

PORT = 8799


def _get(path):
    return json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=1).read())


def main():
    srv = TeamGalleryServer()
    threading.Thread(target=lambda: srv.run(host="127.0.0.1", port=PORT), daemon=True).start()

    for _ in range(60):
        try:
            if _get("/health").get("ok"):
                break
        except Exception:
            time.sleep(0.1)
    else:
        raise SystemExit("gallery did not come up")

    def fake_send(self, content, from_agent="harness", on_chunk=None):
        self.messages.append({"role": "user", "content": content})
        text = f"[{self.name}] ack"
        if on_chunk:
            for tok in text.split(" "):
                on_chunk(tok + " ")
        r = AgentResult(text=text, duration_ms=5)
        self.messages.append({"role": "assistant", "content": r.text})
        return r

    Conversation.send = fake_send

    spec = {
        "name": "intg",
        "task": "",
        "team_dir": tempfile.mkdtemp(prefix="caveteams_intg_"),
        "agents": [{"name": "writer", "backend": "minimax", "system_prompt": "w"}],
    }
    # the on-the-fly call: spin a team wired to the live gallery
    h = build_team(spec, gallery_url=f"http://127.0.0.1:{PORT}")
    h.deliver("leader", "writer", "go")
    time.sleep(0.4)  # let the fire-and-forget POSTs land

    health = _get("/health")
    # team_spawned + agent_added + dispatched + response = 4 events should have reached the gallery
    assert health["buffered"] >= 4, health
    print(f"INTEGRATION PASS — live team reached the running gallery over HTTP: "
          f"{health['buffered']} events buffered, ready for any browser on /ws")


if __name__ == "__main__":
    main()
