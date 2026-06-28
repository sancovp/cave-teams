#!/usr/bin/env python3
"""SDNA chain ontology, native: homoiconic chain nesting + chain_from_spec (JSON → real ontology). NO API."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams import topologies as T

seen = []


class L(Link):
    def __init__(self, name):
        self.name = name

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        ctx["output"] = f"[{self.name}]"
        return LinkResult(LinkStatus.SUCCESS, ctx)


class NeverApprove(L):
    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        ctx["approved"] = False
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    # homoiconic nesting: a Chain is a Link, so chains nest
    seen.clear()
    await T.chain(L("a"), T.chain(L("b"), L("c")), L("d")).execute({"goal": "x"})
    assert seen == ["a", "b", "c", "d"], seen
    print("  chain (homoiconic)  a→(b→c)→d ✓", seen)

    # chain_from_spec: SDNA ChainTool JSON → real Chain of Links (mock leaf_factory, no API)
    seen.clear()
    spec = {"type": "chain", "name": "c", "links": [
        {"type": "config_link", "name": "p"}, {"type": "config_link", "name": "q"}]}
    await T.chain_from_spec(spec, leaf_factory=lambda cfg: L(cfg["name"])).execute({"goal": "run"})
    assert seen == ["p", "q"], seen
    print("  chain_from_spec     SDNA JSON → Chain of Links ✓", seen)

    # eval_chain from spec (max_cycles=1, never approves → BLOCKED after one cycle)
    seen.clear()
    espec = {"type": "eval_chain", "name": "e",
             "links": [{"type": "config_link", "name": "w"}],
             "evaluator": {"type": "config_link", "name": "crit"}, "max_cycles": 1}
    factory = lambda cfg: (NeverApprove(cfg["name"]) if cfg["name"] == "crit" else L(cfg["name"]))
    r = await T.chain_from_spec(espec, leaf_factory=factory).execute({"goal": "x"})
    assert seen == ["w", "crit"] and r.status == LinkStatus.BLOCKED, (seen, r.status)
    print("  eval_chain_from_spec  w→crit, max_cycles gate ✓", seen)

    print("SDNA-CHAIN PASS — homoiconic chain · chain_from_spec · eval_chain (chain-ontology native)")


if __name__ == "__main__":
    asyncio.run(main())
