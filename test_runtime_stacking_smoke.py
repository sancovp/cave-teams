#!/usr/bin/env python3
"""Runtime stacking — agent = team = Link. Apply notation + composing a TeamRuntime inside a real
chain-ontology Chain alongside AgentLinks. NO API."""
import asyncio
import tempfile

from cave_teams import build_team, Conversation, AgentResult, as_agent, AgentLink
from cave_teams.chain_ontology import Chain

seen = []


def fake_send(self, content, from_agent="harness", on_chunk=None):
    seen.append(self.name)
    self.messages.append({"role": "user", "content": content})
    r = AgentResult(text=f"[{self.name}]<{content[:18]}>", duration_ms=1)
    self.messages.append({"role": "assistant", "content": r.text})
    return r


Conversation.send = fake_send


def spec(names):
    return {"name": "rt", "concurrent": False, "team_dir": tempfile.mkdtemp(prefix="ct_rt_"),
            "agents": [{"name": n, "backend": "minimax", "system_prompt": ""} for n in names]}


def test_apply_notation():
    seen.clear()
    inner = as_agent("inner", spec(["x", "y"]), lambda h: h.wire_chain(["x", "y"]))
    out = inner("hello")                          # apply notation: a team called like a function
    assert seen == ["x", "y"], seen
    assert "[y]" in out, out
    print("  apply notation    team(msg) → sub-team x→y ✓", out)


def test_ontology_stacking():
    seen.clear()
    mid = as_agent("mid", spec(["x", "y"]), lambda h: h.wire_chain(["x", "y"]))   # a team...
    comp = Chain("outer", [AgentLink("a"), mid, AgentLink("b")])                   # ...as a Link in a Chain
    asyncio.run(comp.execute({"goal": "go"}))
    assert seen == ["a", "x", "y", "b"], seen     # the TeamRuntime expanded into its sub-team
    print("  ontology stacking Chain([AgentLink a, TeamRuntime mid(x→y), AgentLink b]) ✓", seen)


def main():
    test_apply_notation()
    test_ontology_stacking()
    print("RUNTIME STACKING PASS — agent = team = Link (apply notation · ontology composition)")


if __name__ == "__main__":
    main()
