#!/usr/bin/env python3
"""Phase 4 — the DSL: agent runtimes as algebra expressions (>> ; · | ∥ · dove ⋈). NO API.
Each expression is checked to be observationally equal to its algebra-function form."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams import algebra as Alg
from cave_teams.dsl import dove
from cave_teams.dovetail import DovetailModel, HermesConfigInput

seen = []


class M(Link):
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
        ctx.update(self.sets)
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def run(link, ctx=None):
    seen.clear()
    r = await link.execute(ctx if ctx is not None else {"goal": "x"})
    return r, list(seen)


async def main():
    a, b, c, d = M("a"), M("b"), M("c"), M("d")

    # >> sequential, and it flattens
    expr = a >> b >> c
    from cave_teams.chain_ontology import Chain
    assert type(expr) is Chain and len(expr.links) == 3, "a>>b>>c flattens to one Chain([a,b,c])"
    _, s = await run(expr)
    assert s == ["a", "b", "c"], s
    print("  >>  a>>b>>c  flat Chain, runs in order ✓", s)

    # STRUCTURAL associativity: >> flattens both operands → a flat normal form (not just behavioural)
    assert (a >> (b >> c)).links == ((a >> b) >> c).links == [a, b, c]
    assert ((a | b) | c).links == (a | (b | c)).links            # | flat too (commutative monoid)
    g = Alg.gate(a, b)
    nested = a >> g >> c
    assert len(nested.links) == 3 and type(nested.links[1]).__name__ == "EvalChain"  # gate keeps its boundary
    print("  >>  structural associativity: (a>>(b>>c)).links == ((a>>b)>>c).links ✓")

    # | parallel
    _, sp = await run(a | b)
    assert set(sp) == {"a", "b"}
    print("  |   a|b      parallel ✓")

    # mixed expression == its algebra form (observational equality)
    seen.clear(); r1 = await (a >> (b | c) >> d).execute({"goal": "x"}); s1 = list(seen)
    seen.clear(); r2 = await Alg.seq(a, Alg.par(b, c), d).execute({"goal": "x"}); s2 = list(seen)
    assert s1 == s2 and r1.context["output"] == r2.context["output"] == "[d]", (s1, s2)
    print("  mix a>>(b|c)>>d  ≡  seq(a, par(b,c), d) ✓", s1)

    # dovetail in the notation
    src = M("src", sets={"result": {"summary": "S"}})
    dst = M("dst", reads="goal")
    D = DovetailModel(name="d", expected_outputs=["result.summary"],
                      input_map={"goal": HermesConfigInput(source_key="result.summary")})
    await run(src >> dove(D) >> dst)
    assert dst.got == "S", dst.got
    print("  >>  src >> dove(D) >> dst   typed joint in notation ✓")

    print("DSL PASS — >> ; | ∥ dove ⋈ : agent runtimes as algebra expressions")


if __name__ == "__main__":
    asyncio.run(main())
