#!/usr/bin/env python3
"""evolve — the genetic operator: copy a winner's dir (its AIOS, incl. emergent structure) + remove its
knowledge of previous sessions. Plus tournament (N compete, judge picks). NO API."""
import asyncio
import tempfile
from pathlib import Path

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.evolve import evolve, select_winners
from cave_teams.topologies import tournament


def make_winner(base: Path) -> Path:
    """a player dir that DIVERGED — it developed an emergent skill + accumulated session memory."""
    w = base / "winner"
    (w / ".claude/skills/emergent_trick").mkdir(parents=True)
    (w / ".claude/rules").mkdir(parents=True)
    (w / "crafted").mkdir()
    (w / "memory/zettels").mkdir(parents=True)
    (w / "CLAUDE.md").write_text("# Agent winner — advanced, self-modified")
    (w / ".claude/skills/emergent_trick/SKILL.md").write_text("weird off-script trick that won")
    (w / ".claude/rules/00-style.md").write_text("developed house style")
    (w / "crafted/skill_001.md").write_text("a crafted artifact the user bought")
    (w / "memory/zettels/z1.json").write_text('{"id":1,"note":"prev session"}')
    (w / "short_term_memory.jsonl").write_text('{"thought":"what I did last session"}\n')
    return w


def test_evolve():
    base = Path(tempfile.mkdtemp())
    w = make_winner(base)
    [child] = evolve([str(w)], str(base / "gen2"))
    child = Path(child)

    # ARCHITECTURE inherited — the whole evolved AIOS, including the emergent divergence
    assert (child / "CLAUDE.md").exists()
    assert (child / ".claude/skills/emergent_trick/SKILL.md").read_text() == "weird off-script trick that won"
    assert (child / ".claude/rules/00-style.md").exists()
    assert (child / "crafted/skill_001.md").exists()           # crafted capability kept

    # KNOWLEDGE OF PREVIOUS SESSIONS removed — born fresh
    assert not (child / "memory/zettels").exists()
    assert not (child / "short_term_memory.jsonl").exists()
    print("  evolve  dir copied (architecture+emergent kept) · session memory WIPED ✓")

    # selection = top-k (in the real sim: the user's purchases)
    assert select_winners([("a", 10), ("b", 5), ("c", 20)], k=2) == ["c", "a"]
    print("  select  top-k winners (= the user's purchases) ✓")


class Crafter(Link):
    def __init__(self, name, quality):
        self.name = name
        self.quality = quality

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx[f"craft:{self.name}"] = self.quality
        return LinkResult(LinkStatus.SUCCESS, ctx)


class User(Link):
    """the judge = the user's purchase: buys the highest-quality craft."""
    name = "user"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        crafts = {kk.split(":", 1)[1]: vv for kk, vv in ctx.items() if kk.startswith("craft:")}
        ctx["bought"] = max(crafts, key=crafts.get) if crafts else None
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def test_tournament():
    arena = tournament([Crafter("a", 3), Crafter("b", 9), Crafter("c", 5)], User())
    r = await arena.execute({})
    assert r.context["bought"] == "b", r.context.get("bought")   # user bought the best craft
    print("  tournament  N craft ‖ → user buys the best (b) ✓")


if __name__ == "__main__":
    test_evolve()
    asyncio.run(test_tournament())
    print("EVOLVE + TOURNAMENT PASS — the crafter-sim's reproduction + competition")
