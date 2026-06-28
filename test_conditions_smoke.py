#!/usr/bin/env python3
"""
Conditions / topology smoke test — proves the condition-gated, concurrent firing model.
NO API keys needed (mock Conversation.send).

Asserts:
  1. GATE      — an agent with a failing condition does NOT fire until a flag flips it on.
  2. JOIN      — `after("a")` makes an agent wait until another has completed (barrier).
  3. CONCURRENT — two unblocked agents both fire under concurrent dispatch (wait_idle).

Run:
    python3 test_conditions_smoke.py
"""
import tempfile
import threading
import time

from cave_teams import build_team, Conversation, AgentResult
from cave_teams.conditions import when_flag, after


# mock LLM: record fire order; tiny sleep so concurrency is observable
fired = []
_lock = threading.Lock()


def fake_send(self, content, from_agent="harness", on_chunk=None):
    with _lock:
        fired.append(self.name)
    self.messages.append({"role": "user", "content": content})
    time.sleep(0.05)
    r = AgentResult(text=f"[{self.name}] ok", duration_ms=5)
    self.messages.append({"role": "assistant", "content": r.text})
    return r


Conversation.send = fake_send


def team(names, concurrent):
    spec = {
        "name": "cond",
        "concurrent": concurrent,
        "team_dir": tempfile.mkdtemp(prefix="ct_cond_"),
        "agents": [{"name": n, "backend": "minimax", "system_prompt": ""} for n in names],
    }
    return build_team(spec)


def test_gate():
    fired.clear()
    h = team(["c"], concurrent=False)
    h.add_condition("c", when_flag("go"))          # c fires only when flag 'go' is set
    h.send_message("leader", "c", "do C")
    assert "c" not in fired, "c fired before its condition was met!"
    h.set_flag("go")                                # flips → c becomes eligible → fires
    assert fired == ["c"], fired
    print("  1. GATE       — c blocked until flag 'go' set ✓")


def test_join():
    fired.clear()
    h = team(["a", "b"], concurrent=False)
    h.add_condition("b", after("a"))                # b waits for a to complete (barrier)
    h.send_message("leader", "b", "do B")           # blocked — a not done
    assert "b" not in fired, fired
    h.send_message("leader", "a", "do A")           # a fires → done:a → b unblocks → fires
    assert fired == ["a", "b"], fired
    print("  2. JOIN       — b waited for after('a') barrier ✓")


def test_concurrent():
    fired.clear()
    h = team(["x", "y"], concurrent=True)           # real worker threads
    t0 = time.time()
    h.send_message("leader", "x", "go")
    h.send_message("leader", "y", "go")
    assert h.wait_idle(timeout=5), "team did not go idle"
    elapsed = time.time() - t0
    assert set(fired) == {"x", "y"}, fired
    # both ran ~in parallel: wall-clock < 2x a single 0.05s turn (serial would be >= 0.10s)
    print(f"  3. CONCURRENT — x and y both fired, wall-clock {elapsed*1000:.0f}ms (serial≈100ms) ✓")


def main():
    test_gate()
    test_join()
    test_concurrent()
    print("CONDITIONS PASS — condition-gated + concurrent firing works (gate · join · parallel)")


if __name__ == "__main__":
    main()
