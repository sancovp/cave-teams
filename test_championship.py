#!/usr/bin/env python3
"""Championship — replicated RCTs, deterministic (NO API). The epistemic-rigor
rung §7 promises: under NOISE, a single racetrack can render the WRONG causal
verdict in either direction; strict-majority replication converges on truth.

The noise is an explicit table (tag → observed fitness) — simulated world
noise, fully reproducible, no hidden randomness:

  Scenario A (treatment TRULY better: means 5.14 vs 5.71):
    the single race draws an unlucky pair (7 vs 5) → REVERT   [WRONG]
    7 replicates → treatment wins 4/7 → SHIP                  [RIGHT]
  Scenario B (treatment TRULY worthless: means 5.43 vs 3.71):
    the single race draws a lucky pair (4 vs 6) → SHIP        [WRONG]
    7 replicates → treatment wins 1/7 → REVERT                [RIGHT]

Plus the factory wiring: DarkFactory(replicates=7) escalates its causal gate
from Racetrack to Championship; tally + per-replicate verdicts ride the report
and the lineage.
"""
import asyncio
import tempfile

from cave_teams.darkfactory import (CarKind, Championship, DarkFactory,
                                    proposer_from_fn, racetrack)

# tag → observed fitness. Bare control/treatment = the single race's draw;
# @rN = each replicate's independent draw; incumbent/quarantine feed the
# factory's order-0 read and the gate.
TABLE_A = {  # treatment truly better (control mean 5.14, treatment mean 5.71)
    "incumbent": 5, "quarantine": 6,
    "control": 7, "treatment": 5,                       # unlucky single draw
    "control@r0": 7, "treatment@r0": 5,
    "control@r1": 4, "treatment@r1": 6,
    "control@r2": 4, "treatment@r2": 6,
    "control@r3": 6, "treatment@r3": 5,
    "control@r4": 4, "treatment@r4": 6,
    "control@r5": 7, "treatment@r5": 6,
    "control@r6": 4, "treatment@r6": 6,
}
TABLE_B = {  # treatment truly worthless (control mean 5.43, treatment mean 3.71)
    "incumbent": 5, "quarantine": 5,
    "control": 4, "treatment": 6,                       # lucky single draw
    "control@r0": 4, "treatment@r0": 6,
    "control@r1": 6, "treatment@r1": 3,
    "control@r2": 6, "treatment@r2": 3,
    "control@r3": 5, "treatment@r3": 5,                 # tie: counts against
    "control@r4": 6, "treatment@r4": 3,
    "control@r5": 4, "treatment@r5": 3,
    "control@r6": 7, "treatment@r6": 3,
}


def table_kind(table) -> CarKind:
    async def _race(car, workdir, tag="run"):
        return {"tag": tag, "fitness": table[tag], "car": dict(car)}

    async def _viability(car, workdir):
        return {"alive": True, "cause": "pass",
                "telemetry": await _race(car, workdir, tag="quarantine")}

    return CarKind(race=_race, viability=_viability,
                   apply_delta=lambda car, d: {**car, **(d or {}),
                                               "generation": car.get("generation", 0) + 1,
                                               "lineage": []},
                   name="noise-table")


def main():
    td = tempfile.mkdtemp()
    ctrl, cand = {"role": "incumbent"}, {"role": "candidate"}

    # ── Scenario A: single race WRONG-reverts; championship rightly ships ──
    kA = table_kind(TABLE_A)
    single = asyncio.run(racetrack(ctrl, cand, td, kind=kA).execute({}))
    champ = asyncio.run(Championship(ctrl, cand, td, replicates=7,
                                     kind=kA).execute({}))
    print("Scenario A — treatment truly better (means 5.14 vs 5.71):")
    print(f"  single race:  control=7 treatment=5 → {single.context['verdict']}"
          f"   [wrong — an unlucky draw]")
    print(f"  championship: tally {champ.context['tally']['ships']}–"
          f"{champ.context['tally']['reverts']} → {champ.context['verdict']}"
          f"   [right] (mean {champ.context['race']['control']['fitness']} vs "
          f"{champ.context['race']['treatment']['fitness']})")
    assert single.context["verdict"] == "REVERT"
    assert champ.context["verdict"] == "SHIP"
    assert champ.context["tally"] == {"ships": 4, "reverts": 3, "replicates": 7}

    # ── Scenario B: single race WRONG-ships; championship rightly reverts ──
    kB = table_kind(TABLE_B)
    single = asyncio.run(racetrack(ctrl, cand, td, kind=kB).execute({}))
    champ = asyncio.run(Championship(ctrl, cand, td, replicates=7,
                                     kind=kB).execute({}))
    print("Scenario B — treatment truly worthless (means 5.43 vs 3.71):")
    print(f"  single race:  control=4 treatment=6 → {single.context['verdict']}"
          f"   [wrong — a lucky draw]")
    print(f"  championship: tally {champ.context['tally']['ships']}–"
          f"{champ.context['tally']['reverts']} → {champ.context['verdict']}"
          f"   [right]")
    assert single.context["verdict"] == "SHIP"
    assert champ.context["verdict"] == "REVERT"
    assert champ.context["tally"]["ships"] == 1

    # ── the factory escalates: replicates=7 makes Championship the causal gate ──
    factory = DarkFactory({"role": "incumbent", "generation": 0, "lineage": []},
                          workdir=td, kind=kA, replicates=7)
    rep = asyncio.run(factory.cycle(proposer_from_fn(
        lambda ctx: {"role": "candidate"})))
    print("Factory at Championship order (replicates=7):")
    print(f"  verdict={rep['verdict']} tally={rep['tally']} "
          f"replicate_verdicts={rep['replicate_verdicts']}")
    assert rep["verdict"] == "SHIP" and rep["tally"]["ships"] == 4
    assert len(rep["replicate_verdicts"]) == 7
    assert factory.car["generation"] == 1
    assert factory.car["lineage"][-1]["tally"]["ships"] == 4
    print("  car evolved through a replicated causal gate; tally in lineage ✓")

    print("\nCHAMPIONSHIP PASS — the rigor ladder is real: the same noise that "
          "fools a single RCT in BOTH directions (wrong revert, wrong ship) is "
          "corrected by strict-majority replication. Order 3 is one more "
          "constructor over the same atoms.")


if __name__ == "__main__":
    main()
