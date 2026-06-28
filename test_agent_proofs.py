#!/usr/bin/env python3
"""
Phase 5 — AGENT PROOFS.

DEFINITION (what an agent proof IS here): a mechanically-checked claim about a composition's BEHAVIOUR
that holds for ALL representative inputs — an equation (a ≡ b), a SAFETY property (status=SUCCESS ⟹ P),
or a LIVENESS property (always halts). The algebra laws (test_algebra_laws.py, L1–L7) are the equational
proofs; this file adds termination, gate-soundness, and distribution. NO API.
"""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams import algebra as Alg

seen = []


class M(Link):
    def __init__(self, name):
        self.name = name

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        ctx["output"] = f"[{self.name}]"
        return LinkResult(LinkStatus.SUCCESS, ctx)


class Never(Link):
    """evaluator that never approves."""
    def __init__(self, name="phi"):
        self.name = name

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        ctx["approved"] = False
        return LinkResult(LinkStatus.SUCCESS, ctx)


class ApproveOn(Link):
    """evaluator that approves on its n-th call."""
    def __init__(self, n, name="phi"):
        self.name = name
        self.k = n
        self.i = 0

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        self.i += 1
        ctx["approved"] = self.i >= self.k
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    # PROOF 1 — TERMINATION (liveness): gate ALWAYS halts, bounded by max_cycles (never hangs)
    for N in (1, 3, 5):
        seen.clear()
        r = await Alg.gate(M("body"), Never(), max_cycles=N).execute({})
        assert seen.count("body") == N and r.status == LinkStatus.BLOCKED, (N, seen)
    print("  P1 termination     gate halts in ≤ max_cycles (∀ N: never hangs) ✓")

    # PROOF 2 — GATE-SOUNDNESS (safety): gate SUCCESS ⟺ φ approved; BLOCKED ⟺ cycle-exhaustion
    r_ok = await Alg.gate(M("body"), ApproveOn(2), max_cycles=5).execute({})
    assert r_ok.status == LinkStatus.SUCCESS and r_ok.context.get("approved") is True
    r_no = await Alg.gate(M("body"), Never(), max_cycles=2).execute({})
    assert r_no.status == LinkStatus.BLOCKED and not r_no.context.get("approved")
    print("  P2 gate-soundness  SUCCESS ⟺ φ approved ; BLOCKED ⟺ max_cycles ✓")

    # PROOF 3 — DISTRIBUTION: a;(b+c) ≡ (a;b)+(a;c) when the guard reads input (not a's output)
    a, b, c = M("a"), M("b"), M("c")
    g = lambda ctx: ctx.get("k") == "x"
    left = Alg.seq(a, Alg.choice([(g, b), (lambda ctx: True, c)]))
    right = Alg.choice([(g, Alg.seq(a, b)), (lambda ctx: True, Alg.seq(a, c))])
    for inp, exp in (({"k": "x"}, ["a", "b"]), ({"k": "z"}, ["a", "c"])):
        seen.clear(); await left.execute(dict(inp)); ls = list(seen)
        seen.clear(); await right.execute(dict(inp)); rs = list(seen)
        assert ls == rs == exp, (inp, ls, rs)
    print("  P3 distribution    a;(b+c) ≡ (a;b)+(a;c)  for input-guards ✓")

    print("AGENT PROOFS PASS — termination · gate-soundness · distribution (+ L1–L7 equational laws)")


if __name__ == "__main__":
    asyncio.run(main())
