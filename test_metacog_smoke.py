#!/usr/bin/env python3
"""metacog_shell — self-improving stack: executor→observer→meta[STATIC]→skill_editor, compounds. NO API."""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.metacog import metacog_shell


class Executor(Link):
    """does work — quality improves with the skills it has accumulated."""
    name = "executor"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx["work"] = len(ctx.get("skills", [])) + 1          # more skills → better work (compounding)
        return LinkResult(LinkStatus.SUCCESS, ctx)


class Observer(Link):
    """extracts one new domain skill each cycle (keyed by cycle number, not by reading the
    executor's `work` value — this stub doesn't inspect the trace, it just names the skill)."""
    name = "observer"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx["extracted_skills"] = [f"skill_c{ctx.get('cycle', 0)}"]
        return LinkResult(LinkStatus.SUCCESS, ctx)


class Meta(Link):
    """STATIC fixed point: evaluates METHODOLOGY, never touches the accumulating skills (grounds drift)."""
    name = "meta"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx["assessment"] = "methodology-ok"
        return LinkResult(LinkStatus.SUCCESS, ctx)


class SkillEditor(Link):
    name = "skill_editor"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        ctx["persisted"] = len(ctx.get("skills", []))
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    shell = metacog_shell(Executor(), Observer(), Meta(), skill_editor=SkillEditor(), cycles=3)
    r = await shell.execute({})
    c = r.context

    # compounding: one skill extracted per cycle → 3 total
    assert c["skills"] == ["skill_c1", "skill_c2", "skill_c3"], c["skills"]
    # executor IMPROVES as skills accumulate (work = 1, 2, 3)
    assert [h["work"] for h in c["_cycles"]] == [1, 2, 3], [h["work"] for h in c["_cycles"]]
    print("  compound  executor improves with accumulated skills: work 1→2→3 ✓")

    # the STATIC meta ran every cycle and grounded (assessment present, skills untouched by it)
    assert all(h["meta_assessment"] == "methodology-ok" for h in c["_cycles"])
    print("  anchor    static meta evaluated methodology each cycle (grounds the recursion) ✓")

    # skill_editor persisted the accumulated skills after all cycles
    assert c["persisted"] == 3
    print("  persist   skill_editor persisted 3 accumulated skills ✓")

    print("METACOG PASS — executor→observer→meta[STATIC]→skill_editor, compounding (separate from gameworld)")


if __name__ == "__main__":
    asyncio.run(main())
