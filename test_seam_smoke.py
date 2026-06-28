#!/usr/bin/env python3
"""
Smoke test for the cave-teams event seam + adaptor — NO API keys / LLM needed.

Monkeypatches Conversation.send to canned text, builds a team via the adaptor (concurrent=False
for determinism), drives it with send_message (the gated path), and asserts every boundary
streamed through the EventBus to BOTH listeners (the in-memory capture + the on-disk FileListener),
including token-level 'stream' deltas (which the FileListener skips).

Run:
    python3 test_seam_smoke.py
"""
import json
import os
import tempfile

from cave_teams import build_team, Conversation, AgentResult


def main():
    captured = []

    def cap(ev):
        captured.append(ev.to_dict())

    # --- avoid live LLM: canned echo response, streaming tokens through on_chunk ---
    def fake_send(self, content, from_agent="harness", on_chunk=None):
        self.messages.append({"role": "user", "content": content})
        text = f"[{self.name}] ack: {content[:30]}"
        if on_chunk:
            for tok in text.split(" "):
                on_chunk(tok + " ")
        r = AgentResult(text=text, duration_ms=5)
        self.messages.append({"role": "assistant", "content": r.text})
        return r

    Conversation.send = fake_send

    team_dir = tempfile.mkdtemp(prefix="caveteams_smoke_")
    spec = {
        "name": "smoke",
        "concurrent": False,          # deterministic single-threaded dispatch
        "team_dir": team_dir,
        "agents": [
            {"name": "writer", "backend": "minimax", "system_prompt": "you write"},
            {"name": "reviewer", "backend": "minimax", "system_prompt": "you review"},
        ],
    }

    h = build_team(spec, on_event=cap)
    # send from the (unregistered) leader → each worker fires once, no peer loop
    h.send_message("leader", "writer", "write a haiku")
    h.send_message("leader", "reviewer", "review this haiku")

    kinds = [e["kind"] for e in captured]
    assert "team_spawned" in kinds, kinds
    assert kinds.count("agent_added") == 2, kinds
    assert "message" in kinds, kinds
    assert kinds.count("dispatched") == 2, kinds
    assert kinds.count("response") == 2, kinds

    # token-level streaming flowed through the seam
    stream_n = kinds.count("stream")
    assert stream_n >= 2, kinds

    # FileListener persists coarse events but SKIPS token spam ('stream')
    ev_path = os.path.join(team_dir, "events.jsonl")
    assert os.path.exists(ev_path), "events.jsonl missing"
    file_events = [json.loads(l) for l in open(ev_path) if l.strip()]
    file_kinds = [e["kind"] for e in file_events]
    assert "stream" not in file_kinds, "stream tokens should NOT be persisted"
    assert len(file_events) == len(captured) - stream_n, (len(file_events), len(captured), stream_n)

    # frontend imports + HTTP listener fails safe when no gallery is up
    from cave_teams.frontend import HttpFrontendListener, TeamGalleryServer  # noqa: F401
    HttpFrontendListener("http://127.0.0.1:1")(
        type("E", (), {"to_dict": lambda s: {"team": "x", "kind": "ping"}})()
    )

    print(f"PASS — {len(captured)} events (incl {stream_n} stream tokens): {kinds}")


if __name__ == "__main__":
    main()
