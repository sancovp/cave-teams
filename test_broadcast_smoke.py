"""Broadcast + concurrent teammates (Isaac's pattern: 'a single message or a broadcast to all or
some ... the teammates can run while the leader runs'). Scripted leader, staggered fake runtimes,
no LLMs: broadcast to both → alerted as EACH finishes (fast one first) → wait for the slow one →
end. Also: messaging an in-flight teammate is guardrail-blocked, and wait-with-nothing-running is
guardrail-blocked."""
import asyncio
import tempfile

from cave_teams import Team, AgentRef, par, run_team
from cave_teams.runner import Proposal, check_proposal
from cave_teams.wiring import compile_to_edges


class Duo(Team):
    op = None  # not registered — a test-local team

    def build(self):
        return par(AgentRef("fast"), AgentRef("slow"))


class StaggeredRuntime:
    def __init__(self, name, delay):
        self.name, self.delay = name, delay

    async def run(self, prompt: str) -> str:
        await asyncio.sleep(self.delay)
        return f"{self.name} done"


def scripted_leader(script):
    """A leader that replays `script` (a list of Proposals), recording the ctx it saw each step."""
    seen = []

    def propose(ctx):
        seen.append({"alert": ctx.get("alert"), "in_flight": list(ctx.get("in_flight", [])),
                     "error": ctx.get("error")})
        return script[min(len(seen) - 1, len(script) - 1)] if not ctx.get("error") else script[-1]
    return propose, seen


def test_broadcast_then_wait():
    with tempfile.TemporaryDirectory() as td:
        script = [
            Proposal(to=["fast", "slow"], prompt="go"),      # broadcast to BOTH at once
            Proposal(wait=True),                             # first alert seen → wait for the other
            Proposal(end=True, report="both done"),
        ]
        leader, seen = scripted_leader(script)
        res = run_team(Duo({}), "task", leader,
                       {"fast": StaggeredRuntime("fast", 0.01), "slow": StaggeredRuntime("slow", 0.15)},
                       td)
        assert res["ok"], res
        assert res["report"] == "both done"
        finishes = [t["finished"] for t in res["transcript"] if "finished" in t]
        assert finishes == ["fast", "slow"], finishes        # alerted as EACH finishes, fast first
        # step 2's ctx: fast already finished, slow STILL in flight — concurrency was real
        assert seen[1]["alert"]["finished"] == "fast"
        assert seen[1]["in_flight"] == ["slow"]
        assert seen[1]["alert"]["still_running"] == ["slow"]
        dispatches = [m for m in res["messages"] if m["kind"] == "dispatch"]
        responses = [m for m in res["messages"] if m["kind"] == "response"]
        assert len(dispatches) == 2 and len(responses) == 2
    print("ok  broadcast to all → alerted per finish (fast first, slow still running) → wait → end")


def test_guardrails_inflight_and_wait():
    edges = compile_to_edges(par(AgentRef("a"), AgentRef("b")))
    # messaging an in-flight teammate is blocked
    err = check_proposal(Proposal(to="a", prompt="again"), ["a", "b"], edges, [], in_flight={"a"})
    assert err and "STILL RUNNING" in err, err
    # wait with nothing running is blocked
    err = check_proposal(Proposal(wait=True), ["a", "b"], edges, [], in_flight=set())
    assert err and "no one to wait for" in err, err
    # broadcast with one bad name names the bad one
    err = check_proposal(Proposal(to=["a", "ghost"], prompt="x"), ["a", "b"], edges, [])
    assert err and "ghost" in err, err
    print("ok  guardrails: in-flight re-dispatch, empty wait, bad broadcast member all blocked")


if __name__ == "__main__":
    test_broadcast_then_wait()
    test_guardrails_inflight_and_wait()
    print("\nBROADCAST TESTS PASSED")
