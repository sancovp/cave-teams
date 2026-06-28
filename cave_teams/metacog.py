"""
metacog.py — the Metacog Shell: a self-improving observation stack with a STATIC fixed point.

A SEPARATE pattern from the gameworld/crafter loop (per Isaac — metacog is NOT what runs inside the
gameworld). Four roles in a peer chain:

    executor    — does the work (with the skills accumulated so far)
    observer    — reads the executor's trace, EXTRACTS domain skills (these accumulate → executor improves)
    meta        — the STATIC fixed point: evaluates the observer's METHODOLOGY (not the domain content);
                  grounds the recursion so "improvement" can't drift into not-actually-better
    skill_editor (optional) — after all cycles, PERSISTS the accumulated skills

It compounds across cycles: cycle N+1's executor starts with cycle N's extracted skills. The `meta` is the
SAME Link every cycle — the anchor that does not self-modify. (Files=truth / messages=pointers is the
out-of-band detail; here the trace is threaded as context.)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .chain_ontology import Link, LinkResult, LinkStatus


class MetacogShell(Link):
    def __init__(self, executor: Link, observer: Link, meta: Link,
                 skill_editor: Optional[Link] = None, cycles: int = 1,
                 skills_key: str = "skills", name: str = "metacog"):
        self.executor = executor
        self.observer = observer
        self.meta = meta                       # STATIC: the same Link every cycle (the fixed point)
        self.skill_editor = skill_editor
        self.cycles = cycles
        self.skills_key = skills_key
        self.name = name

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx0 = dict(context) if context else {}
        skills: List[Any] = list(ctx0.get(self.skills_key, []))     # accumulates across cycles (compounds)
        history = []

        for c in range(self.cycles):
            inp = dict(ctx0)
            inp[self.skills_key] = list(skills)
            inp["cycle"] = c + 1
            ectx = (await self.executor.execute(inp)).context or inp           # executor → trace
            octx = (await self.observer.execute(ectx)).context or ectx         # observer → extracts skills
            mctx = (await self.meta.execute(octx)).context or octx             # meta[STATIC] → methodology

            extracted = octx.get("extracted_skills", [])
            skills.extend(extracted)                                            # the compounding step
            history.append({"cycle": c + 1, "work": ectx.get("work"),
                            "extracted": extracted, "meta_assessment": mctx.get("assessment")})

        final = dict(ctx0)
        final[self.skills_key] = skills
        final["_cycles"] = history
        if self.skill_editor is not None:                                       # persist after all cycles
            final = (await self.skill_editor.execute(dict(final))).context or final
        final["output"] = skills
        return LinkResult(status=LinkStatus.SUCCESS, context=final)

    def describe(self, depth: int = 0) -> str:
        tail = " →skill_editor" if self.skill_editor is not None else ""
        return "  " * depth + f'metacog "{self.name}" ×{self.cycles}: executor→observer→meta[STATIC]{tail}'


def metacog_shell(executor: Link, observer: Link, meta: Link,
                  skill_editor: Optional[Link] = None, cycles: int = 1,
                  skills_key: str = "skills", name: str = "metacog") -> MetacogShell:
    return MetacogShell(executor, observer, meta, skill_editor, cycles=cycles, skills_key=skills_key, name=name)


__all__ = ["metacog_shell", "MetacogShell"]
