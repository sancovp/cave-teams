"""Container test (needs cave): the headless cave-server construction primitives —
make_headless_cave (CAVEAgent via __new__ + selective init) + the ephemeral server start/stop."""
import tempfile
from pathlib import Path

from cave_teams.server import make_headless_cave, EphemeralTeamServer


def _cfg():
    from cave.core.config import CAVEConfig
    from cave.core.models import CaveAgentEntry
    base = Path(tempfile.mkdtemp())
    return CAVEConfig(agents=[CaveAgentEntry(name="alice", agent_type="chat")],
                      data_dir=base / "d", hook_dir=base / "h", host="127.0.0.1", port=0)


def test_headless_construct():
    cave = make_headless_cave(_cfg())
    assert "alice" in cave.cave_agents, list(cave.cave_agents)
    print("ok  headless CAVEAgent constructed (no Sanctuary/heart/world); cave_agents:", list(cave.cave_agents))


def test_server_start_stop():
    cave = make_headless_cave(_cfg())
    srv = EphemeralTeamServer(cave).start()
    srv.stop()
    print("ok  ephemeral CAVEHTTPServer start + teardown")


if __name__ == "__main__":
    test_headless_construct()
    test_server_start_stop()
    print("\nFACTORY (headless cave server) TESTS PASSED")
