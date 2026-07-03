"""
evolve.py — the genetic operator (the crafter-sim's reproduction), the clean version of the CRUDE way.

An agent's architecture IS its whole directory — its AIOS: CLAUDE.md, .claude/skills (INCLUDING the weird
emergent ones the agent developed when it diverged off-script and did awesome stuff anyway), rules, crafted
artifacts — everything it organically became. Reproduction:

    copy the winner's dir          — inherit the EVOLVED architecture (no pattern imposed; divergence kept)
    remove its knowledge of prior   — wipe the session/episodic memory → the child re-engages the advanced
      sessions                        dir COLD, free to re-diverge

You inherit the altitude (the dir), you regrow the content (the memory). The child is born ADVANCED (the
dir) and born FRESH (no memory). Selection = the USER's purchases (the sound external gate). This was crude
(`cp -r` + `rm`) when run with real Claude Code teams; here it is one primitive.

NOTE the distinction from a season-advance: a season keeps the SAME agent (its zettels persist); EVOLVE
makes a NEW agent that must not remember the parent's sessions — so the episodic memory is wiped.
"""

from __future__ import annotations

import glob
import shutil
from pathlib import Path
from typing import List, Optional, Sequence, Tuple, Union

# what counts as "knowledge of previous sessions" — removed on reproduction (the ARCHITECTURE is kept:
# CLAUDE.md, .claude/skills, .claude/rules, crafted/ all survive).
DEFAULT_SESSION_MEMORY = [
    "short_term_memory.jsonl",
    ".memory",
    "memory/zettels",
    "memory/short_term_memory.jsonl",
    "**/*.session.jsonl",
]


def evolve_dir(winner_dir: Union[str, Path], child_dir: Union[str, Path],
               wipe: Optional[Sequence[str]] = None) -> str:
    """Copy a winner's whole agent dir → child_dir (inherit the AIOS, incl. emergent structure), then
    remove its knowledge of previous sessions (the session-memory paths). Returns child_dir."""
    winner_dir, child_dir = Path(winner_dir), Path(child_dir)
    if not winner_dir.is_dir():
        raise FileNotFoundError(f"evolve_dir: winner dir does not exist: {winner_dir}")
    if child_dir.exists():
        shutil.rmtree(child_dir)
    shutil.copytree(winner_dir, child_dir)                       # inherit the evolved architecture
    for pat in (wipe if wipe is not None else DEFAULT_SESSION_MEMORY):
        for p in glob.glob(str(child_dir / pat), recursive=True):  # remove knowledge of previous sessions
            pp = Path(p)
            if pp.is_dir():
                shutil.rmtree(pp, ignore_errors=True)
            elif pp.exists():
                pp.unlink()
    return str(child_dir)


def evolve(winner_dirs: Sequence[Union[str, Path]], out_dir: Union[str, Path],
           prefix: str = "gen", wipe: Optional[Sequence[str]] = None) -> List[str]:
    """Reproduce a generation: copy each winner's dir into out_dir/{prefix}_{i} and wipe its session
    memory. Returns the child dirs — the next generation, born advanced (the dir) + memory-free."""
    if not winner_dirs:
        raise ValueError("evolve: no winners — an empty generation cannot reproduce "
                         "(check the judge's scores / select_winners k)")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    return [evolve_dir(w, out / f"{prefix}_{i}", wipe=wipe) for i, w in enumerate(winner_dirs)]


def select_winners(ranked: Sequence[Union[str, Tuple[Union[str, Path], float]]], k: int = 1) -> List[str]:
    """The selection step — top-k. In the real sim this IS the user's purchases (the external gate); here
    a pluggable ranking. Accepts a list of dirs, or of (dir, score) pairs (sorted by score desc).
    TIES break by input order (stable sort) — with equal scores the earlier-listed dir survives;
    pass a pre-shuffled/pre-ordered list if that bias matters."""
    if ranked and isinstance(ranked[0], (tuple, list)):
        return [str(d) for d, _ in sorted(ranked, key=lambda x: x[1], reverse=True)[:k]]
    return [str(d) for d in list(ranked)[:k]]


__all__ = ["evolve", "evolve_dir", "select_winners", "DEFAULT_SESSION_MEMORY"]
