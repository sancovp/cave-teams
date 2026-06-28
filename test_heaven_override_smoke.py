#!/usr/bin/env python3
"""
Override a REAL CAVE agent's run with a TEAM run — the homoiconic close, live against cave.core.

CAVE's Agent.set_runtime accepts "any object with run(message)/handle_message/__call__". A
TeamRuntime has all three, so a whole cave-team drops straight in as an agent's runtime: the CAVE
agent's run() now executes a team. (A real heaven agent / BaseHeavenAgent is the same shape — a
TeamRuntime substitutes wherever a heaven agent's run goes, and vice-versa.) NO API keys needed.
"""
import asyncio
import tempfile

from cave_teams import as_agent, Conversation, AgentResult
from cave_teams import topologies as T

seen = []


def fake_send(self, content, from_agent="harness", on_chunk=None):
    seen.append(self.name)
    self.messages.append({"role": "user", "content": content})
    r = AgentResult(text=f"[{self.name}]<{content[:18]}>", duration_ms=1)
    self.messages.append({"role": "assistant", "content": r.text})
    return r


Conversation.send = fake_send


def spec(names):
    return {"name": "sq", "concurrent": False, "team_dir": tempfile.mkdtemp(prefix="ct_ov_"),
            "agents": [{"name": n, "backend": "minimax", "system_prompt": ""} for n in names]}


def main():
    # a whole team behind one agent
    team_rt = as_agent("squad", spec(["x", "y"]), lambda h: h.wire_chain(["x", "y"]))

    # pull up a real CAVE agent (the virtualization layer heaven agents run under) ...
    from cave.core.agent import Agent
    a = Agent()
    # ... and OVERRIDE its runtime with the team
    a.set_runtime(team_rt)

    out = asyncio.run(a.run("do the thing"))     # CAVE Agent.run() now delegates to a TEAM
    assert seen == ["x", "y"], seen
    assert "[y]" in (out or ""), out
    print("OVERRIDE PASS — cave.core.Agent.run() executed a TEAM (x→y):", seen, "| out:", out)


if __name__ == "__main__":
    main()
