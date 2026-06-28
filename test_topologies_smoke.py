#!/usr/bin/env python3
"""Topology menu, chain-ontology-native: each builder returns a composed Link. NO API."""
import asyncio
import time

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams import topologies as T

seen = []


class L(Link):
    def __init__(self, name, delay=0.0):
        self.name = name
        self.delay = delay

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        if self.delay:
            await asyncio.sleep(self.delay)
        seen.append(self.name)
        ctx["output"] = f"[{self.name}]"
        ctx[f"output:{self.name}"] = ctx["output"]
        return LinkResult(LinkStatus.SUCCESS, ctx)


class Approver(Link):
    """Evaluator: approves (sets ctx['approved']) on its 2nd call — a loop terminator."""
    def __init__(self, name, key="approved"):
        self.name = name
        self.key = key
        self.n = 0

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        self.n += 1
        ctx[self.key] = self.n >= 2
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    seen.clear()
    r = await T.pipeline(L("a"), L("b"), L("c")).execute({"goal": "x"})
    assert seen == ["a", "b", "c"] and r.context["output"] == "[c]", seen
    print("  pipeline    A→B→C (Chain) ✓", seen)

    seen.clear()
    t0 = time.time()
    r = await T.fan_out(L("x", 0.1), L("y", 0.1)).execute({"goal": "x"})
    el = time.time() - t0
    assert set(seen) == {"x", "y"} and el < 0.18, (seen, el)
    print(f"  fan_out     parallel {el*1000:.0f}ms (ConcurrentChain) ✓")

    seen.clear()
    r = await T.map_reduce([L("w1"), L("w2")], L("synth")).execute({"goal": "x"})
    assert "w1" in seen and "w2" in seen and seen[-1] == "synth", seen
    assert "output:w1" in r.context and "output:w2" in r.context, "reducer must see both workers"
    print("  map_reduce  scatter→gather (reducer saw both workers) ✓", seen)

    seen.clear()
    r = await T.loop_refine(L("worker"), Approver("critic")).execute({"goal": "x"})
    assert seen == ["worker", "critic", "worker", "critic"], seen
    print("  loop_refine worker↔critic until approved (EvalChain) ✓", seen)

    seen.clear()
    r = await T.duo(L("ar"), L("po"), Approver("ov")).execute({"goal": "x"})
    assert seen == ["ar", "po", "ov", "ar", "po", "ov"], seen
    print("  duo         A→P→OVP loop (EvalChain) ✓", seen)

    seen.clear()
    rt = T.router([(lambda c: c.get("flag") == "b", L("B")), (lambda c: True, L("C"))])
    await rt.execute({"flag": "b"})
    assert seen == ["B"], seen
    seen.clear()
    await rt.execute({"flag": "z"})
    assert seen == ["C"], seen
    print("  router      conditional branch ✓")

    print("TOPOLOGIES PASS — pipeline · fan_out · map_reduce · loop_refine · duo · router (chain-ontology native)")


if __name__ == "__main__":
    asyncio.run(main())
