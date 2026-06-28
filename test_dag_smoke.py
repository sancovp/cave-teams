#!/usr/bin/env python3
"""dag — the general partial-order scheduler. PROVES seq and par are its two limits. NO API."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams import algebra as Alg
from cave_teams.dag import dag

seen = []
inputs = {}
MARK = {"a", "b", "c", "d"}


class M(Link):
    def __init__(self, name):
        self.name = name

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        inputs[self.name] = {kk for kk in ctx if kk in MARK}   # which upstream outputs this node saw
        ctx[self.name] = True
        ctx["output"] = f"[{self.name}]"
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    # LIMIT 1 — linear deps ≡ seq
    seen.clear()
    rd = await dag({"a": M("a"), "b": M("b"), "c": M("c")}, {"b": ["a"], "c": ["b"]}).execute({})
    sd = list(seen)
    seen.clear()
    rs = await Alg.seq(M("a"), M("b"), M("c")).execute({})
    ss = list(seen)
    assert sd == ss == ["a", "b", "c"] and rd.context["output"] == rs.context["output"] == "[c]", (sd, ss)
    print("  LIMIT  dag(linear deps) ≡ seq(a,b,c) ✓", sd)

    # LIMIT 2 — no deps ≡ par
    seen.clear()
    await dag({"a": M("a"), "b": M("b"), "c": M("c")}, {}).execute({})
    sdp = set(seen)
    seen.clear()
    await Alg.par(M("a"), M("b"), M("c")).execute({})
    spp = set(seen)
    assert sdp == spp == {"a", "b", "c"}
    print("  LIMIT  dag(no deps) ≡ par(a,b,c) ✓")

    # GENERAL — diamond a→{b,c}→d: a first, d last, d sees ALL upstream outputs
    seen.clear(); inputs.clear()
    r = await dag({"a": M("a"), "b": M("b"), "c": M("c"), "d": M("d")},
                  {"b": ["a"], "c": ["a"], "d": ["b", "c"]}).execute({})
    assert seen[0] == "a" and seen[-1] == "d" and set(seen) == {"a", "b", "c", "d"}, seen
    assert {"a", "b", "c"} <= inputs["d"], inputs["d"]          # dataflow folded along the edges
    assert inputs["a"] == set() and inputs["b"] == {"a"}
    assert r.context["_dag"] == {"a": "success", "b": "success", "c": "success", "d": "success"}
    print("  DAG    diamond a→{b,c}→d: order + dataflow-fold ✓")

    # cycle → ERROR (never hangs)
    rc = await dag({"a": M("a"), "b": M("b")}, {"a": ["b"], "b": ["a"]}).execute({})
    assert rc.status == LinkStatus.ERROR and "cycle" in rc.error
    print("  GUARD  cycle → ERROR (no hang) ✓")

    # unknown dependency → ValueError at construction
    try:
        dag({"a": M("a")}, {"a": ["nope"]})
        assert False, "expected ValueError"
    except ValueError:
        pass
    print("  GUARD  unknown dependency → ValueError ✓")

    print("DAG PASS — seq and par are the two limits; blockedBy in between")


if __name__ == "__main__":
    asyncio.run(main())
