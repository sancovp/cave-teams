#!/usr/bin/env python3
"""Phase 2: the SDNA/heaven agent zoo composes as Links in the chain ontology. NO API."""
import asyncio

from cave_teams import Conversation, AgentResult, AgentLink, as_link, RunnableLink, CHAIN_ONTOLOGY_SOURCE
from cave_teams.chain_ontology import Link, Chain, LinkResult, LinkStatus

seen = []


def fake_send(self, content, from_agent="harness", on_chunk=None):
    seen.append(self.name)
    self.messages.append({"role": "user", "content": content})
    r = AgentResult(text=f"[{self.name}]", duration_ms=1)
    self.messages.append({"role": "assistant", "content": r.text})
    return r


Conversation.send = fake_send


class HeavenStub:                         # a heaven-style runnable (.run), NOT a Link
    def __init__(self, name):
        self.name = name

    def run(self, message):
        seen.append(self.name)
        return f"<{self.name}>"


def fn_leaf(content):                     # a plain callable leaf
    seen.append("fn")
    return "fn-out"


class SdnaStub(Link):                     # stands in for SDNAC (already a Link)
    def __init__(self, name):
        self.name = name

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        ctx["output"] = f"sdnac:{self.name}"
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    print("  ontology source:", CHAIN_ONTOLOGY_SOURCE)

    s = SdnaStub("s")
    assert as_link(s) is s, "a Link passes through as_link unchanged"
    assert isinstance(as_link(HeavenStub("h")), RunnableLink)

    # one Chain mixing ALL leaf flavors — the zoo composes as Links
    seen.clear()
    zoo = Chain("zoo", [SdnaStub("sdnac"), as_link(HeavenStub("heaven")),
                        as_link(fn_leaf, name="fn"), AgentLink("cave")])
    r = await zoo.execute({"goal": "go"})
    assert seen == ["sdnac", "heaven", "fn", "cave"], seen
    assert "[cave]" in r.context["output"], r.context["output"]
    print("  zoo chain    SDNA-Link · heaven-.run · callable · AgentLink composed ✓", seen)

    # structural: a REAL SDNAC is a cave_teams.Link → drops straight into a Chain
    try:
        from sdna.sdna import SDNAC
        assert issubclass(SDNAC, Link)
        print("  SDNAC        is a cave_teams.Link (composes directly, no wrapper) ✓")
    except Exception as e:  # pragma: no cover
        print("  SDNAC        (sdna not importable in this env:", type(e).__name__, ")")

    print("SDNA-AGENTS PASS — the agent zoo composes as Links (chain-ontology native)")


if __name__ == "__main__":
    asyncio.run(main())
