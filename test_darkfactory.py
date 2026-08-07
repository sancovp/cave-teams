#!/usr/bin/env python3
"""DarkFactory — the ladder of orders, deterministic (NO API). Proves the composed
Racetrack(Formula1Stable(World)) end-to-end:

  CYCLE 1  the proposal is DEVELOPED IN A NESTED DEV-WORLD (world_as_agent): a dev
           agent crafts a real .md whose CONTENT is the delta, another BUYS it —
           the traded artifact IS the accepted proposal. Gate passes → the RCT
           (control ask=80 fitness 1 vs treatment ask=40 fitness 2) → SHIP.
  CYCLE 2  a lethal delta (ask=0 → every post guard-rejected → market dead) DIES
           at the quarantine gate; a second lineage (ask=200 → unaffordable) DIES
           too; the third (ask=40 = incumbent) survives the gate but TIES the
           race → REVERT. Ties never ship.

Fitness = completed trades over 5 rounds (deterministic drivers ⇒ zero-noise RCT).
"""
import asyncio
import json
import os
import tempfile

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.gameworld import world_as_agent
from cave_teams.skillcraft import (SkillcraftWorld, initial_state, craft_skill,
                                   record_test)
from cave_teams.darkfactory import DarkFactory, new_car, proposer_from_fn


# ── the dev-world (order-0 nested in the proposer seat): scripted devs TRADE the change ──
class _DevSeller(Link):
    """Crafts tune_ask_price.md whose CONTENT is the delta JSON, tests it, posts it."""
    def __init__(self, name, root):
        self.name, self.root, self._done = name, root, False

    async def execute(self, context=None, **_):
        c = dict(context or {})
        if not self._done:
            self._done = True
            sp = craft_skill(self.root, self.name, "tune_ask_price",
                             json.dumps({"ask_price": 40}))
            tid = record_test(self.root, self.name, sp, "pass")
            c["action"] = {"type": "trade_post", "skill_path": sp, "price": 10,
                           "test_id": tid, "rarity": "uncommon",
                           "description": "lower the ask to raise throughput"}
        else:
            c["action"] = {"type": "wait"}
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class _DevBuyer(Link):
    def __init__(self, name):
        self.name = name

    async def execute(self, context=None, **_):
        c = dict(context or {})
        listings = c.get("board", {}).get("trade_board", [])
        c["action"] = ({"type": "trade_buy", "listing_id": listings[0]["listing_id"]}
                       if listings else {"type": "search"})
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


def dev_world_proposer(dev_root, quests_root):
    """The §1 shape: dev-world = agents coming up with a change TOGETHER by trading
    it. world_as_agent makes the whole dev-WoS play as the proposer seat; the
    derive step reads the last TRADED artifact's file — the sold .md IS the delta."""
    world = SkillcraftWorld(
        agents={"dev_1": _DevSeller("dev_1", dev_root), "dev_2": _DevBuyer("dev_2")},
        agents_root=dev_root, quests_root=quests_root,
        rounds=2, seasons=1, name="dev-world")

    def derive_delta(inner_board):
        hist = inner_board.get("trade_history", [])
        if not hist:
            return {}                          # nothing agreed → empty delta
        last = hist[-1]
        path = os.path.join(dev_root, last["seller"], last["skill_path"])
        return json.loads(open(path).read())

    wa = world_as_agent(world, derive_delta, name="dev_world_seat")

    class _Seeded(Link):                       # seed the inner board, then delegate
        name = "dev_world_seat"

        async def execute(self, context=None, **_):
            c = dict(context or {})
            c.setdefault("inner_board", initial_state(["dev_1", "dev_2"]))
            return await wa.execute(c)

    return _Seeded()


def main():
    with tempfile.TemporaryDirectory() as td:
        factory = DarkFactory(new_car(ask_price=80, starting_gold=100),
                              workdir=td, rounds=5, max_attempts=3)

        # ── CYCLE 1 — dev-world develops the change; gate passes; RCT ships ──
        dev_root = os.path.join(td, "devworld", "agents")
        quests = os.path.join(td, "devworld", "quests")
        os.makedirs(quests, exist_ok=True)
        rep1 = asyncio.run(factory.cycle(dev_world_proposer(dev_root, quests)))
        print("CYCLE 1 — the dev-world's traded artifact is the proposal:")
        print(f"  incumbent telemetry: fitness={rep1['telemetry']['fitness']} "
              f"(ask=80: one affordable buy)")
        print(f"  delta traded in the dev-world: {rep1['candidate']['ask_price']=}")
        print(f"  race: control={rep1['race']['control']['fitness']} "
              f"treatment={rep1['race']['treatment']['fitness']} "
              f"→ {rep1['verdict']}")
        assert rep1["telemetry"]["fitness"] == 1
        assert rep1["telemetry"]["gold_conserved"] is True
        assert rep1["candidate"]["ask_price"] == 40
        assert rep1["extinct"] == []
        assert rep1["race"]["control"]["fitness"] == 1
        assert rep1["race"]["treatment"]["fitness"] == 2
        assert rep1["verdict"] == "SHIP"
        assert factory.car["ask_price"] == 40 and factory.car["generation"] == 1
        assert factory.car["lineage"][-1]["verdict"] == "SHIP"
        print("  car evolved: generation 1, ask_price 40 ✓\n")

        # ── CYCLE 2 — two lineages DIE at the gate; the survivor TIES → REVERT ──
        attempts = [{"ask_price": 0},          # lethal: guard rejects every post
                    {"ask_price": 200},        # lethal: never affordable
                    {"ask_price": 40}]         # survivor — but == incumbent

        def scripted(ctx):
            return attempts[ctx.get("cycle", 1) - 1]

        rep2 = asyncio.run(factory.cycle(proposer_from_fn(scripted)))
        print("CYCLE 2 — deaths at the gate, then a tie:")
        for e in rep2["extinct"]:
            print(f"  ☠ lineage extinct: delta={e['delta']} — {e['cause']}")
        print(f"  survivor: ask={rep2['candidate']['ask_price']} → race: "
              f"control={rep2['race']['control']['fitness']} "
              f"treatment={rep2['race']['treatment']['fitness']} "
              f"→ {rep2['verdict']}")
        assert len(rep2["extinct"]) == 2
        assert "market dead" in rep2["extinct"][0]["cause"]
        assert rep2["extinct"][0]["delta"] == {"ask_price": 0}
        assert "market dead" in rep2["extinct"][1]["cause"]
        assert rep2["verdict"] == "REVERT"                 # tie never ships
        assert factory.car["ask_price"] == 40 and factory.car["generation"] == 1
        assert factory.car["lineage"][-1]["verdict"] == "REVERT"
        assert factory.car["lineage"][-1]["extinct"] == rep2["extinct"]
        print("  car unchanged (generation 1) — ties and deaths never ship ✓\n")

    print("DARKFACTORY PASS — Racetrack(Formula1Stable(World)): the dev-world's "
          "traded artifact proposed the change, the quarantine gate killed two "
          "lineages, the RCT shipped a strict win and reverted a tie. "
          "Selection at every order; the car is the only thing that persists.")


if __name__ == "__main__":
    main()
