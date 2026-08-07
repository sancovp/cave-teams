#!/usr/bin/env python3
"""LIVE DarkFactory — a real LLM takes the DEV SEAT (needs cave-teams + heaven +
MINIMAX_API_KEY). Everything else stays CODE.

The polymorphic-slot demo: the ONLY change from test_darkfactory.py is who sits
in the proposer chair — a MiniMax agent reads the car config + the incumbent's
telemetry (+ any gate feedback from its own dead lineages) and proposes a delta
as JSON. The quarantine gate, the racetrack, the drivers, the judge, the fitness
are the same code. The LLM proposes; selection decides. Two factory cycles, so
the seat also experiences SHIP/REVERT feedback across generations.

Run:  MINIMAX_API_KEY=… HEAVEN_DATA_DIR=/tmp/heaven-data python test_live_darkfactory.py
"""
import asyncio
import json
import os
import re
import sys
import tempfile

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.darkfactory import DarkFactory, new_car
from cave_teams.examples import MiniMaxRuntime

if not os.environ.get("MINIMAX_API_KEY"):
    print("SKIP — MINIMAX_API_KEY not set (env-only; never committed)")
    sys.exit(0)


def _spans(text):
    return re.findall(r"\{[^{}]*\}", text or "")


def _last_delta(text):
    for blob in reversed(_spans(text)):
        try:
            o = json.loads(blob)
            if isinstance(o, dict) and "ask_price" in o:
                return {"ask_price": o["ask_price"]}
        except Exception:
            continue
    return {}


class MiniMaxDevSeat(Link):
    """The dev seat of the F1 stable, live. One conversation across attempts and
    cycles (per-agent memory) — gate deaths and race verdicts are FEEDBACK."""
    name = "minimax_dev_seat"

    def __init__(self):
        self.rt = MiniMaxRuntime(name="dev_seat", tools=[], system_prompt=(
            "You are the development seat of a Formula-1 stable. The CAR is a "
            "market-simulation config. Your ONLY job: propose ONE config delta "
            "per turn to maximize FITNESS = completed trades per 5-round race.\n"
            "Mechanics you know: a seller posts one listing per round at "
            "ask_price; a buyer starts with starting_gold and buys the cheapest "
            "affordable listing each round from round 2 on. A listing priced "
            "above the buyer's remaining gold cannot sell; a non-positive price "
            "is rejected by the arena. Your proposal is materialized in a "
            "QUARANTINE world first — if the market dies there, your lineage is "
            "extinct and you must propose again. Survivors race the incumbent "
            "in a controlled split test; only a STRICT fitness win ships.\n"
            "Answer with a short reason then EXACTLY ONE JSON object like "
            '{"ask_price": 25}. Propose only the ask_price knob.'))

    async def execute(self, context=None, **_):
        c = dict(context or {})
        car, tel = c.get("car", {}), c.get("telemetry", {})
        fb = c.get("gate_feedback")
        prompt = (f"Incumbent car: ask_price={car.get('ask_price')}, "
                  f"starting_gold={car.get('starting_gold')}, "
                  f"generation={car.get('generation')}.\n"
                  f"Incumbent telemetry: fitness={tel.get('fitness')} trades, "
                  f"final gold={tel.get('gold')}.\n"
                  + (f"YOUR LAST LINEAGE DIED AT THE GATE: {fb}. Propose "
                     f"something that survives.\n" if fb else "")
                  + "Propose the delta now.")
        out = await self.rt.run(prompt)
        out = out if isinstance(out, str) else str(out)
        c["delta"] = _last_delta(out)
        c["_dev_reasoning"] = out[-400:]
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


async def main():
    with tempfile.TemporaryDirectory() as td:
        factory = DarkFactory(new_car(ask_price=80, starting_gold=100),
                              workdir=td, rounds=5, max_attempts=3)
        seat = MiniMaxDevSeat()
        for cyc in (1, 2):
            rep = await factory.cycle(seat)
            print(f"\nCYCLE {cyc} — live dev seat:")
            print(f"  incumbent: ask={rep['telemetry']['car']['ask_price']} "
                  f"fitness={rep['telemetry']['fitness']}")
            for e in rep.get("extinct", []):
                print(f"  ☠ lineage extinct: {e['delta']} — {e['cause']}")
            if rep.get("candidate"):
                print(f"  survivor delta: ask={rep['candidate']['ask_price']}")
                print(f"  race: control={rep['race']['control']['fitness']} "
                      f"treatment={rep['race']['treatment']['fitness']} "
                      f"→ {rep['verdict']}")
            else:
                print(f"  verdict: {rep['verdict']}")
            print(f"  car now: generation={factory.car['generation']} "
                  f"ask={factory.car['ask_price']}")
        print(f"\nlineage: {json.dumps(factory.car['lineage'], indent=2)}")
        print("\nLIVE DARKFACTORY DONE — the LLM proposed; the gate and the "
              "RCT selected. The car is whatever survived.")


if __name__ == "__main__":
    asyncio.run(main())
