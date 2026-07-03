"""
sim.py — the Economic Crafter Sim: the engine that is the COMPILER and the RESEARCH LAB at once (an ant
farm for XYZ).

It composes the team primitives into one generational loop:

    each generation:
      crafters CRAFT in competition  → the USER buys the best        (tournament; the sound external gate)
      → select the winners (= the purchases)
      → EVOLVE them: copy each winner's dir (its AIOS, incl. emergent divergence) + wipe session memory
      → respawn the next generation on those dirs

Point it at any domain XYZ → it breeds agents good at XYZ. The output = the winning lineage = a trained
prompt-engineer agent. (Stage 2, separate: deploy that agent into a domain-gameworld to farm skills.)

It is a COMPILER (domain XYZ → a trained agent) and a RESEARCH LAB (selection discovers what works) — same
machine, two registers. The loop here is the HARNESS; the variation that drives improvement comes from the
agents themselves — real LLM crafters re-engaging the inherited advanced dir COLD and re-diverging. With
mock crafters the loop runs and the winners' architecture propagates; real agents make it *improve*.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .chain_ontology import Link
from .topologies import tournament
from .evolve import evolve, select_winners


def _name(d) -> str:
    return Path(str(d)).name


async def crafter_sim(population_dirs: List[str],
                      spawn: Callable[[str], Link],
                      judge: Link,
                      generations: int = 3,
                      workdir: str = "/tmp/crafter_sim",
                      k: int = 1,
                      on_generation: Optional[Callable[[int, list, list], None]] = None) -> Dict[str, Any]:
    """Run the sim for `generations`.
      spawn(dir) -> a crafter Link backed by that AIOS dir (its .name should be the dir's basename);
      judge      -> the USER: reads the crafts, writes ctx['scores'] = {crafter_name: score} (+ 'bought').
    Returns {lineage, history, best}. `best` is the trained prompt-engineer (the winning lineage head)."""
    dirs = [str(d) for d in population_dirs]
    history: List[Dict[str, Any]] = []
    best = dirs[0] if dirs else None

    for gen in range(generations):
        crafters = [spawn(d) for d in dirs]
        result = await tournament(crafters, judge).execute({"generation": gen})        # compete → user buys
        scores = (result.context or {}).get("scores", {})
        ranked = [(d, scores.get(_name(d), 0)) for d in dirs]
        winners = select_winners(ranked, k=k)                                          # = the purchases
        best = winners[0] if winners else best
        history.append({"generation": gen, "bought": (result.context or {}).get("bought"),
                        "ranked": ranked, "winners": winners})
        if on_generation:
            on_generation(gen, ranked, winners)
        if not winners:                    # extinct lineage — stop, don't loop forever on nothing
            history[-1]["stopped"] = "no winners — lineage extinct"
            break
        dirs = evolve(winners, str(Path(workdir) / f"gen{gen + 1}"))                    # copy dirs + wipe memory

    return {"lineage": dirs, "history": history, "best": best}


__all__ = ["crafter_sim"]
