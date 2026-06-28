#!/usr/bin/env python3
"""
Frontend smoke test — proves the gallery serves the page and that POST /emit
fans the event out to every connected /ws client (the on-the-fly display path).

Uses a fake ws client captured in _ws_clients so we exercise the REAL /emit route
+ the REAL _send_all fan-out without the flaky in-portal ws transport (the wire
transport itself is the same proven pattern as promptworld's /ws).
"""
import json

from fastapi.testclient import TestClient
from cave_teams.frontend import TeamGalleryServer, FrontendListener


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, data):
        self.sent.append(data)


def main():
    srv = TeamGalleryServer()
    client = TestClient(srv.app)

    assert client.get("/health").json()["ok"] is True
    page = client.get("/").text
    assert "cave-teams" in page and "/ws" in page, "gallery page missing"

    fake = FakeWS()
    srv._ws_clients.add(fake)

    # REAL /emit route → REAL _send_all fan-out → connected client gets it
    ev = {"team": "demo", "kind": "dispatched", "agent": "writer",
          "data": {"content": "write a haiku"}, "ts": 0}
    assert client.post("/emit", json=ev).json()["ok"] is True
    assert len(fake.sent) == 1, fake.sent
    got = json.loads(fake.sent[0])
    assert got["team"] == "demo" and got["kind"] == "dispatched" and got["agent"] == "writer", got

    # FrontendListener(server) — the in-process listener a Harness bus would call
    FrontendListener(srv)(type("E", (), {"to_dict": lambda s: {"team": "demo", "kind": "response",
                                                               "agent": "writer", "data": {}, "ts": 1}})())
    assert len(srv._recent) >= 2  # buffered for late-joining browsers

    print("FRONTEND PASS — page served, /emit fanned out to /ws client, FrontendListener buffered")


if __name__ == "__main__":
    main()
