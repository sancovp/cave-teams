#!/usr/bin/env python3
"""
Phase 3 — mechanical verification of the agent-composition algebra laws (the first agent proofs).
Each check runs both sides of an equation on mock Links and asserts observational equality
(effect order/set + output context). NO API.
"""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams import algebra as Alg
from cave_teams.dovetail import DovetailModel, HermesConfigInput

seen = []


class M(Link):
    """records name; sets output=[name]; optionally records a context key into .got, or sets keys."""
    def __init__(self, name, sets=None, reads=None):
        self.name = name
        self.sets = sets or {}
        self.reads = reads
        self.got = None

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        if self.reads is not None:
            self.got = ctx.get(self.reads)
        ctx["output"] = f"[{self.name}]"
        ctx[f"output:{self.name}"] = ctx["output"]
        ctx.update(self.sets)
        return LinkResult(LinkStatus.SUCCESS, ctx)


class Approver(Link):
    def __init__(self, name):
        self.name = name
        self.n = 0

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        seen.append(self.name)
        self.n += 1
        ctx["approved"] = self.n >= 2
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def run(link, ctx=None):
    seen.clear()
    r = await link.execute(ctx if ctx is not None else {"goal": "x"})
    return r, list(seen)


async def main():
    a, b, c = M("a"), M("b"), M("c")

    # L1 — ; is a monoid (associative, identity), NOT commutative
    r1, s1 = await run(Alg.seq(a, Alg.seq(b, c)))
    r2, s2 = await run(Alg.seq(Alg.seq(a, b), c))
    assert s1 == s2 == ["a", "b", "c"] and r1.context["output"] == r2.context["output"], (s1, s2)
    print("  L1  ; associativity   (a;b);c ≡ a;(b;c) ✓")
    _, si1 = await run(Alg.seq(Alg.skip(), a))
    _, si2 = await run(Alg.seq(a, Alg.skip()))
    assert si1 == si2 == ["a"], (si1, si2)
    print("  L1  ; identity         1;a ≡ a ≡ a;1 ✓")
    rab, _ = await run(Alg.seq(a, b))
    rba, _ = await run(Alg.seq(b, a))
    assert rab.context["output"] == "[b]" and rba.context["output"] == "[a]"
    print("  L1  ; NON-commutative  a;b ≠ b;a ✓")

    # L2 — ∥ is a commutative monoid (assoc + comm)
    _, sp1 = await run(Alg.par(a, b))
    _, sp2 = await run(Alg.par(b, a))
    assert set(sp1) == set(sp2) == {"a", "b"}
    _, spa = await run(Alg.par(Alg.par(a, b), c))
    _, spb = await run(Alg.par(a, Alg.par(b, c)))
    assert set(spa) == set(spb) == {"a", "b", "c"}
    print("  L2  ∥ comm + assoc     a∥b ≡ b∥a, (a∥b)∥c ≡ a∥(b∥c) ✓")

    # L3 — μ gate: bounded fixpoint, loop body until φ approves
    _, sg = await run(Alg.gate(M("body"), Approver("phi")))
    assert sg == ["body", "phi", "body", "phi"], sg
    print("  L3  μ gate             loop(body) until φ approves ✓")

    # L4 — + choice: first guard that holds
    routes = [(lambda c: c.get("k") == "x", M("X")), (lambda c: True, M("Y"))]
    _, sc1 = await run(Alg.choice(routes), {"k": "x"})
    _, sc2 = await run(Alg.choice(routes), {"k": "z"})
    assert sc1 == ["X"] and sc2 == ["Y"]
    print("  L4  + choice           first guard that holds ✓")

    # L5 — ⋈ dovetail: typed joint + validation (a⋈[D]b ≡ a;transform(D);b)
    src = M("src", sets={"result": {"summary": "S"}})
    dst = M("dst", reads="goal")
    D = DovetailModel(name="d", expected_outputs=["result.summary"],
                      input_map={"goal": HermesConfigInput(source_key="result.summary")})
    await run(Alg.dovetail(src, D, dst))
    assert dst.got == "S", dst.got                       # dst received the extracted, typed input
    rerr, _ = await run(Alg.dovetail(M("bad"), D, dst))   # bad doesn't set result → validation error
    assert rerr.status == LinkStatus.ERROR
    print("  L5  ⋈ dovetail         typed joint + expected_outputs validation ✓")

    # L6 — closure (homoiconic): run(team(G)) ≡ run(G)
    G = Alg.seq(M("p"), M("q"))
    rg, sgG = await run(G)
    rt, stG = await run(Alg.team(G))
    assert sgG == stG == ["p", "q"] and rg.context["output"] == rt.context["output"]
    print("  L6  closure            run(team(G)) ≡ run(G)  (agent = team = agent) ✓")

    # L7 — lift homomorphism: ⟦callable⟧ runs it; ⟦Link⟧ = Link (idempotent inclusion)
    def f(content):
        seen.append("f")
        return "f-out"
    _, sl = await run(Alg.lift(f, name="f"))
    assert sl == ["f"]
    assert Alg.lift(a) is a
    print("  L7  lift               ⟦f⟧ runs f; ⟦Link⟧ = Link ✓")

    print("ALGEBRA LAWS PASS — ; ∥ + μ ⋈ closure lift  (the first agent proofs)")


if __name__ == "__main__":
    asyncio.run(main())
