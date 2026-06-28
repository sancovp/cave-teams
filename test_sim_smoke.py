#!/usr/bin/env python3
"""crafter_sim — the whole engine: compete → user buys → select → evolve, over generations. NO API.
Mock crafters craft proportional to a 'genome' file in their dir; this proves the loop THREADS the
winner's architecture forward and wipes memory each generation. (Real LLM crafters add the variation
that makes it IMPROVE; the mock shows propagation + mechanics.)"""
import asyncio
import tempfile
from pathlib import Path

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.sim import crafter_sim


def make_pop(base: Path):
    dirs = []
    for nm, genome in (("a", 3), ("b", 9), ("c", 5)):
        d = base / nm
        d.mkdir(parents=True)
        (d / "CLAUDE.md").write_text(f"# agent {nm}")
        (d / "genome.txt").write_text(str(genome))           # the inherited 'architecture' signal
        (d / "short_term_memory.jsonl").write_text('{"prev":"session"}\n')
        dirs.append(str(d))
    return dirs


class DirCrafter(Link):
    """crafts proportional to the genome it inherited in its dir (re-reads the dir cold each gen)."""
    def __init__(self, d):
        self.dir = d
        self.name = Path(d).name

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx[f"craft:{self.name}"] = int((Path(self.dir) / "genome.txt").read_text())
        return LinkResult(LinkStatus.SUCCESS, ctx)


class User(Link):
    """the judge = the user's purchase: scores every craft, buys the best (the sound external gate)."""
    name = "user"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        crafts = {kk.split(":", 1)[1]: vv for kk, vv in ctx.items() if kk.startswith("craft:")}
        ctx["scores"] = crafts
        ctx["bought"] = max(crafts, key=crafts.get) if crafts else None
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    base = Path(tempfile.mkdtemp())
    pop = make_pop(base)
    out = await crafter_sim(pop, spawn=DirCrafter, judge=User(),
                            generations=3, workdir=str(base / "run"), k=1)

    # gen 0: user bought the best craft (b, genome 9)
    assert out["history"][0]["bought"] == "b", out["history"][0]["bought"]
    assert len(out["history"]) == 3
    print("  gen0   user bought the best crafter (b=9) ✓")

    # the winning architecture propagated through every generation; the head is the trained agent
    best = Path(out["best"])
    assert (best / "genome.txt").read_text() == "9"            # winner's architecture survived the lineage
    assert not (best / "short_term_memory.jsonl").exists()      # each generation born memory-free
    assert (best / "CLAUDE.md").exists()
    print("  loop   winner architecture propagated, memory wiped each gen ✓", out["best"].split("/")[-2:])

    print("CRAFTER-SIM PASS — compete → user-buys → select → evolve → next gen (the ant farm for XYZ)")


if __name__ == "__main__":
    asyncio.run(main())
