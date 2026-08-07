#!/usr/bin/env python3
"""LIVE SkillFactory — the FRESH-MODEL TEST-GATE, for real (needs cave-teams +
heaven + MINIMAX_API_KEY). The dark factory's #1, occupied:

The car is a PROSE skill — pure instructions, no code block. Its executor is a
FRESH MiniMax session PER CALL (no history, no dev context): it receives ONLY
the skill document + one input, must follow the document EXACTLY, and its
output is compared by code. That seat is the sound mint the WoS economy needs
(the fix for self-minted test_ids). The dev seat is a separate MiniMax
conversation that sees the artifact + the failing INPUTS (never the expected
outputs — anti-Goodhart) and proposes an edited document between <ARTIFACT>
tags. Gate, race, comparison, verdicts: all code.

Honest note: LLM executors are stochastic — the same doc can score differently
across runs, so a single race is noisier than the subprocess kind (replicates
per arm are the production answer; the topology is unchanged). This run
reports what actually happened, whatever that is.

Run:  MINIMAX_API_KEY=… HEAVEN_DATA_DIR=… python test_live_skillfactory.py
"""
import asyncio
import json
import os
import re
import sys
import tempfile

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.darkfactory import DarkFactory
from cave_teams.skillcar import new_skill_car, skill_kind
from cave_teams.examples import MiniMaxRuntime

if not os.environ.get("MINIMAX_API_KEY"):
    print("SKIP — MINIMAX_API_KEY not set (env-only; never committed)")
    sys.exit(0)

# 5 cases; the incumbent's PROSE BUG (ignore any address containing uppercase)
# fails the two mixed-case ones when followed exactly.
BATTERY = [
    {"input": "reach me at bob@x.com or alice@y.org", "expected": "alice@y.org,bob@x.com"},
    {"input": "no emails here at all", "expected": ""},
    {"input": "dupes: a@b.co a@b.co c@d.io", "expected": "a@b.co,c@d.io"},
    {"input": "mixed Bob@X.com and carol@z.net today", "expected": "bob@x.com,carol@z.net"},
    {"input": "UPPER ADMIN@SITE.ORG only", "expected": "admin@site.org"},
]

INCUMBENT = """# Skill: extract-emails (prose edition)
You will be given a text. Follow these steps exactly:
1. Find every email address in the text — BUT ignore any email address that
   contains one or more uppercase letters; such addresses must be skipped.
2. Lowercase the addresses you kept.
3. Remove duplicates and sort them alphabetically.
4. Output ONLY the addresses joined by commas, with no spaces. If none, output
   an empty string.
"""


def fresh_judge(artifact: str, task_input: str, workdir: str):
    """THE FRESH SEAT: a brand-new session per call — no history, no dev
    context. Sees only the document + the input. This is gate #1."""
    async def _run():
        rt = MiniMaxRuntime(name="fresh_gate", tools=[], temperature=0.0,
                            system_prompt=(
                                "You are a skill executor. Follow the skill "
                                "document EXACTLY as written, even where it "
                                "seems suboptimal or wrong — fidelity to the "
                                "document is your only job. Output ONLY the "
                                "final result, no commentary, no quotes."))
        out = await rt.run(f"SKILL DOCUMENT:\n{artifact}\n\nINPUT:\n{task_input}"
                           f"\n\nExecute the skill on the input now.")
        out = (out if isinstance(out, str) else str(out)).strip().strip('"\'')
        # models often say 'empty string' when the answer is empty
        if out.lower() in ("empty string", "(empty string)", "none", '""', "''"):
            out = ""
        return {"ok": True, "output": out}
    return _run()


class MiniMaxSkillDev(Link):
    """The dev seat: one continuing conversation; sees the artifact + failing
    inputs (never expected outputs); proposes the full edited document."""
    name = "skill_dev_seat"

    def __init__(self):
        self.rt = MiniMaxRuntime(name="skill_dev", tools=[], system_prompt=(
            "You are the development seat of a skill factory. The artifact is "
            "a PROSE skill document executed literally by a fresh model. Your "
            "job: edit the document so it scores more correct outputs on the "
            "hidden task battery. You see which INPUTS failed, never the "
            "expected outputs. Reason briefly, then output the COMPLETE edited "
            "document between <ARTIFACT> and </ARTIFACT> tags."))

    async def execute(self, context=None, **_):
        c = dict(context or {})
        car, tel = c.get("car", {}), c.get("telemetry", {})
        fb = c.get("gate_feedback")
        prompt = (f"CURRENT ARTIFACT (generation {car.get('generation')}):\n"
                  f"{car.get('artifact')}\n\n"
                  f"TELEMETRY: fitness={tel.get('fitness')}/{tel.get('cases')} "
                  f"correct.\nFAILING INPUTS:\n"
                  + "\n".join(f"- {i}" for i in tel.get("failing_inputs", []))
                  + (f"\nYOUR LAST LINEAGE DIED AT THE GATE: {fb}\n" if fb else "")
                  + "\nPropose the edited document now.")
        out = await self.rt.run(prompt)
        out = out if isinstance(out, str) else str(out)
        m = re.search(r"<ARTIFACT>(.*?)</ARTIFACT>", out, re.S)
        c["delta"] = {"artifact": m.group(1).strip() + "\n"} if m else {}
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


async def main():
    with tempfile.TemporaryDirectory() as td:
        kind = skill_kind(BATTERY, executor=fresh_judge, require_block=False,
                          name="prose-skill-car")
        factory = DarkFactory(new_skill_car(INCUMBENT, name="extract-emails-prose"),
                              workdir=td, max_attempts=2, kind=kind)
        rep = await factory.cycle(MiniMaxSkillDev())
        print("\nLIVE SKILLFACTORY — the fresh-model gate, occupied:")
        print(f"  incumbent (buggy prose): fitness="
              f"{rep['telemetry']['fitness']}/{rep['telemetry']['cases']}")
        print(f"  failing inputs shown to dev: "
              f"{rep['telemetry']['failing_inputs']}")
        for e in rep.get("extinct", []):
            print(f"  ☠ lineage extinct — {e['cause']}")
        if rep.get("candidate"):
            print(f"  race: control={rep['race']['control']['fitness']} "
                  f"treatment={rep['race']['treatment']['fitness']} "
                  f"→ {rep['verdict']}")
            if rep["verdict"] == "SHIP":
                print("  --- the shipped document ---")
                print("  " + factory.car["artifact"].replace("\n", "\n  ").rstrip())
        else:
            print(f"  verdict: {rep['verdict']}")
        print(f"\n  car: generation={factory.car['generation']}")
        print(f"  lineage: {json.dumps(factory.car['lineage'], indent=2)}")
        print("\nLIVE SKILLFACTORY DONE — a fresh model executed every candidate "
              "purely from its text; the dev seat never saw an expected output; "
              "code compared and decided.")


if __name__ == "__main__":
    asyncio.run(main())
