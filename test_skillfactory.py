#!/usr/bin/env python3
"""SkillFactory — the CODE-LEVEL car, deterministic (NO API). The same
DarkFactory, injected with skill_kind: the artifact (a skill .md whose fenced
python block is its core) is the genome; the delta is a change to the TEXT; the
quarantine executes the artifact for real (subprocess judge); the RCT races
incumbent vs candidate on the factory's task battery.

Proves: a syntax-broken PR DIES at the gate; a cosmetic PR ties → REVERT; a
real fix strictly wins → SHIP; telemetry never leaks expected outputs
(anti-Goodhart); and THE WELD — the shipped artifact becomes a tradeable WoS
asset whose test record is minted on the GATE's verdict, not the crafter's word.
"""
import asyncio
import json
import os
import tempfile

from cave_teams.darkfactory import DarkFactory, proposer_from_fn
from cave_teams.skillcar import new_skill_car, skill_kind, extract_block
from cave_teams.skillcraft import (initial_state, skillcraft_mutator,
                                   craft_skill, record_test)

# the task: extract all email addresses, lowercased, sorted, comma-joined
BATTERY = [
    {"input": "reach me at bob@x.com or alice@y.org", "expected": "alice@y.org,bob@x.com"},
    {"input": "no emails here at all", "expected": ""},
    {"input": "dupes: a@b.co a@b.co c@d.io", "expected": "a@b.co,c@d.io"},
    {"input": "mixed Bob@X.com and carol@z.net today", "expected": "bob@x.com,carol@z.net"},
    {"input": "UPPER ADMIN@SITE.ORG only", "expected": "admin@site.org"},
    {"input": "end of line: zed@qq.dev", "expected": "zed@qq.dev"},
]

INCUMBENT = """# Skill: extract-emails
Extract every email address from the text; output lowercased, sorted, comma-joined.

```python
import re
def solve(text):
    found = re.findall(r"[a-z0-9._%+-]+@[a-z0-9.-]+\\.[a-z]{2,}", text)
    return ",".join(sorted(set(found)))
```
"""                                        # BUG: lowercase-only → misses Bob@X.com etc.

BROKEN = INCUMBENT.replace("def solve(text):", "def solve(text)")   # syntax error

COSMETIC = INCUMBENT.replace("# Skill: extract-emails",
                             "# Skill: extract-emails (v2, nicer prose)")

FIXED = """# Skill: extract-emails
Extract every email address from the text; output lowercased, sorted, comma-joined.
Handles any casing.

```python
import re
def solve(text):
    found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}", text)
    return ",".join(sorted({f.lower() for f in found}))
```
"""


def main():
    with tempfile.TemporaryDirectory() as td:
        kind = skill_kind(BATTERY)
        factory = DarkFactory(new_skill_car(INCUMBENT, name="extract-emails"),
                              workdir=td, max_attempts=3, kind=kind)

        # ── CYCLE 1: broken PR dies; cosmetic PR survives but TIES → REVERT ──
        attempts = [{"artifact": BROKEN}, {"artifact": COSMETIC}]
        rep1 = asyncio.run(factory.cycle(proposer_from_fn(
            lambda ctx: attempts[ctx.get("cycle", 1) - 1])))
        print("CYCLE 1 — a broken PR and a cosmetic PR:")
        print(f"  incumbent fitness: {rep1['telemetry']['fitness']}/"
              f"{rep1['telemetry']['cases']} (lowercase-only bug)")
        for e in rep1["extinct"]:
            print(f"  ☠ lineage extinct — {e['cause']}")
        print(f"  race: control={rep1['race']['control']['fitness']} "
              f"treatment={rep1['race']['treatment']['fitness']} "
              f"→ {rep1['verdict']}")
        assert rep1["telemetry"]["fitness"] == 4          # 2 mixed-case cases fail
        assert len(rep1["extinct"]) == 1
        assert "cannot execute" in rep1["extinct"][0]["cause"]
        assert rep1["verdict"] == "REVERT"                 # cosmetic = tie
        assert factory.car["generation"] == 0
        # anti-Goodhart: telemetry reveals failing INPUTS, never expected outputs
        leaked = [exp for exp in ("alice@y.org,bob@x.com", "bob@x.com,carol@z.net",
                                  "admin@site.org")
                  if any(exp in fi for fi in rep1["telemetry"]["failing_inputs"])]
        assert rep1["telemetry"]["failing_inputs"] and not leaked
        print(f"  telemetry reveals {len(rep1['telemetry']['failing_inputs'])} "
              f"failing inputs, zero expected outputs (anti-Goodhart) ✓\n")

        # ── CYCLE 2: the real fix → strict win → SHIP ──
        rep2 = asyncio.run(factory.cycle(proposer_from_fn(
            lambda ctx: {"artifact": FIXED})))
        print("CYCLE 2 — the real fix:")
        print(f"  race: control={rep2['race']['control']['fitness']} "
              f"treatment={rep2['race']['treatment']['fitness']} "
              f"→ {rep2['verdict']}")
        assert rep2["race"]["control"]["fitness"] == 4
        assert rep2["race"]["treatment"]["fitness"] == 6
        assert rep2["verdict"] == "SHIP"
        assert factory.car["generation"] == 1
        assert "Handles any casing" in factory.car["artifact"]
        assert factory.car["lineage"][-1]["verdict"] == "SHIP"
        print("  car evolved: generation 1, the artifact TEXT is the new genome ✓\n")

        # ── THE WELD: the shipped artifact enters the WoS economy, its test
        #    record minted on the GATE's verdict (the sound mint — no more
        #    self-minted/forgeable test_ids) ──
        wos_root = os.path.join(td, "wos", "agents")
        quests = os.path.join(td, "wos", "quests")
        os.makedirs(quests, exist_ok=True)
        gate_verdict = asyncio.run(kind.viability(factory.car, td))
        assert gate_verdict["alive"]                       # the gate's word…
        sp = craft_skill(wos_root, "factory_1", "extract_emails",
                         factory.car["artifact"])
        tid = record_test(wos_root, "factory_1", sp, "pass",
                          test_id=f"gate_{gate_verdict['telemetry']['fitness']}"
                                  f"of{gate_verdict['telemetry']['cases']}")
        mut = skillcraft_mutator(wos_root, quests)
        st = mut(initial_state(["factory_1", "trader_1"]), "factory_1",
                 {"type": "trade_post", "skill_path": sp, "price": 60,
                  "test_id": tid, "rarity": "rare",
                  "description": "gate-tested email extractor (6/6)"})
        assert len(st["trade_board"]) == 1                 # …is what trade_post trusts
        assert st["trade_board"][0]["test_id"].startswith("gate_6of6")
        print("THE WELD — the shipped artifact is now a WoS listing whose "
              "test_id was minted by the factory's gate (6/6), not by the "
              "crafter's own claim ✓\n")

    print("SKILLFACTORY PASS — the artifact IS the car: broken PRs die at the "
          "quarantine, cosmetic PRs revert on a tie, a real fix ships on a "
          "strict RCT win, telemetry never leaks answers, and the survivor "
          "trades in the WoS economy with a gate-minted test record.")


if __name__ == "__main__":
    main()
