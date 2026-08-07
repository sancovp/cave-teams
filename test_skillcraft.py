#!/usr/bin/env python3
"""SkillcraftWorld — the real WoS economy re-assembled from the atoms. Deterministic (NO API): proves
every execute.sh guard is ported faithfully + a full craft→test→post→buy round + a bounty advance."""
import asyncio
import os
import tempfile

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.skillcraft import (
    SkillcraftWorld, skillcraft_mutator, skillcraft_advance, initial_state,
    craft_skill, record_test, validate_bug,
)


def _expect_reject(mut, state, agent, action, why):
    try:
        mut(state, agent, action)
    except ValueError:
        return
    raise AssertionError(f"guard did NOT fire: {why}")


def test_guards(root, quests):
    mut = skillcraft_mutator(root, quests)
    st = initial_state(["agent_001", "agent_002"])

    # craft a real skill + mint a test record (the embodiment)
    sp = craft_skill(root, "agent_001", "codebase_archaeology", "# skill\nreal executable skill body")
    tid = record_test(root, "agent_001", sp, "pass")

    # trade_post guards
    _expect_reject(mut, st, "agent_001", {"type": "trade_post", "skill_path": sp, "price": 80},
                   "no test_id")
    _expect_reject(mut, st, "agent_001", {"type": "trade_post", "skill_path": sp, "price": 0, "test_id": tid},
                   "non-positive price")
    _expect_reject(mut, st, "agent_001", {"type": "trade_post", "skill_path": "crafted/ghost.md", "price": 80, "test_id": tid},
                   "skill file missing")
    _expect_reject(mut, st, "agent_001", {"type": "trade_post", "skill_path": sp, "price": 80, "test_id": "test_nope"},
                   "test record missing")
    # a test record for a DIFFERENT skill must not authorize this one
    sp2 = craft_skill(root, "agent_001", "other", "# other")
    tid_other = record_test(root, "agent_001", sp2, "pass")
    _expect_reject(mut, st, "agent_001", {"type": "trade_post", "skill_path": sp, "price": 80, "test_id": tid_other},
                   "test record skill_path mismatch")
    # valid post
    st = mut(st, "agent_001", {"type": "trade_post", "skill_path": sp, "price": 80, "test_id": tid,
                               "rarity": "epic", "description": "codebase archaeology"})
    assert len(st["trade_board"]) == 1
    lid = st["trade_board"][0]["listing_id"]
    assert st["trade_board"][0]["test_id"] == tid and st["trade_board"][0]["rarity"] == "epic"

    # trade_buy guards
    _expect_reject(mut, st, "agent_001", {"type": "trade_buy", "listing_id": lid}, "self-buy")
    st["agents"]["agent_002"]["gold"] = 50
    _expect_reject(mut, st, "agent_002", {"type": "trade_buy", "listing_id": lid}, "insufficient gold")
    st["agents"]["agent_002"]["gold"] = 100
    st = mut(st, "agent_002", {"type": "trade_buy", "listing_id": lid})
    assert st["agents"]["agent_002"]["gold"] == 20      # 100 - 80
    assert st["agents"]["agent_001"]["gold"] == 180     # 100 + 80  (atomic, both sides)
    assert st["agents"]["agent_001"]["trades_completed"] == 1
    assert st["agents"]["agent_002"]["trades_completed"] == 1
    assert st["trade_board"] == []                       # listing removed
    assert len(st["trade_history"]) == 1 and st["trade_history"][0]["buyer"] == "agent_002"
    _expect_reject(mut, st, "agent_002", {"type": "trade_buy", "listing_id": lid}, "buy removed listing")

    # quest anti-injection: reward comes from the canonical file, NOT agent input
    os.makedirs(quests, exist_ok=True)
    open(os.path.join(quests, "q_forge.md"), "w").write("# Forge\n## Reward\n120 gold\n")
    _expect_reject(mut, st, "agent_001", {"type": "quest_complete", "quest_id": "q_forge", "skill_path": sp},
                   "complete without accept")
    st = mut(st, "agent_001", {"type": "quest_accept", "quest_id": "q_forge"})
    g0 = st["agents"]["agent_001"]["gold"]
    st = mut(st, "agent_001", {"type": "quest_complete", "quest_id": "q_forge", "skill_path": sp,
                               "reward": 99999})          # <-- injected reward is IGNORED
    assert st["agents"]["agent_001"]["gold"] == g0 + 120, "reward must come from the file, not input"
    assert st["agents"]["agent_001"]["quests_completed"] == 1
    _expect_reject(mut, st, "agent_001", {"type": "quest_accept", "quest_id": "q_forge"}, "re-accept completed")

    # LFG
    st = mut(st, "agent_001", {"type": "lfg_post", "specializations": "recipes", "looking_for": "components"})
    pid = st["lfg_board"][0]["party_id"]
    st = mut(st, "agent_002", {"type": "lfg_join", "party_id": pid})
    assert st["lfg_board"][0]["members"] == ["agent_001", "agent_002"]
    _expect_reject(mut, st, "agent_002", {"type": "lfg_join", "party_id": pid}, "double join")
    _expect_reject(mut, st, "agent_002", {"type": "lfg_join", "party_id": "lfg_ghost"}, "join missing party")

    # challenge: post a fresh listing, agent_002 challenges, self + double blocked
    st = mut(st, "agent_001", {"type": "trade_post", "skill_path": sp, "price": 50, "test_id": tid})
    lid2 = st["trade_board"][0]["listing_id"]
    _expect_reject(mut, st, "agent_001", {"type": "challenge", "listing_id": lid2, "assessment": "x", "reason": "y"},
                   "self challenge")
    st = mut(st, "agent_002", {"type": "challenge", "listing_id": lid2, "assessment": "uncommon", "reason": "thin"})
    assert st["trade_board"][0]["challenges"][0]["challenger"] == "agent_002"
    _expect_reject(mut, st, "agent_002", {"type": "challenge", "listing_id": lid2, "assessment": "x", "reason": "y"},
                   "double challenge")
    print("  guards: trade_post(5) · trade_buy(3) · quest anti-injection · lfg · challenge — ALL fire ✓")


def test_advance_bounty():
    bugs = [{"id": "bug_1", "reporter": "agent_002", "status": "open", "reward_paid": False},
            {"id": "bug_2", "reporter": "agent_002", "status": "open", "reward_paid": False}]
    validate_bug(bugs, "bug_1", "valid")
    validate_bug(bugs, "bug_2", "valid")
    adv = skillcraft_advance(bugs)
    board = initial_state(["agent_001", "agent_002"])
    board["agents"]["agent_001"]["gold"] = 400            # earned during the season
    board["trade_board"] = [{"listing_id": "x"}]
    nxt = adv(board, 2)
    assert nxt["season"]["number"] == 2
    assert nxt["season"]["previous_season"]["number"] == 1
    assert nxt["agents"]["agent_001"]["gold"] == 100      # reset (no bounty)
    assert nxt["agents"]["agent_002"]["gold"] == 300      # 100 floor + 2×100 bounty ON TOP
    assert nxt["trade_board"] == []                        # boards wiped
    assert nxt["season"]["rarity_consensus"]["recipe"] == "epic"   # ratchet carried
    assert all(b["reward_paid"] for b in bugs)             # bounties marked paid
    print("  advance: bounty(2×100 on top of the 100 floor) · reset · boards wiped · ratchet carried ✓")


# a deterministic player: craft+test then post; or buy a named listing
class Scripted(Link):
    def __init__(self, name, root, plan):
        self.name = name; self.root = root; self.plan = plan; self._i = 0
    async def execute(self, ctx=None, **k):
        c = dict(ctx or {})
        board = c.get("board", {})
        act = self.plan(self, board)
        c["action"] = act
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


async def test_full_world(root, quests):
    def a1_plan(self, board):
        # craft a real skill + test, then post it (only once)
        if self._i == 0:
            self._i = 1
            sp = craft_skill(self.root, "agent_001", "recipe_pipeline", "# recipe\ncomposes 2 skills")
            tid = record_test(self.root, "agent_001", sp, "pass")
            return {"type": "trade_post", "skill_path": sp, "price": 40, "test_id": tid, "rarity": "epic"}
        return {"type": "wait"}

    def a2_plan(self, board):
        listings = board.get("trade_board", [])
        if listings:
            return {"type": "trade_buy", "listing_id": listings[0]["listing_id"]}
        return {"type": "search"}

    world = SkillcraftWorld(
        agents={"agent_001": Scripted("agent_001", root, a1_plan),
                "agent_002": Scripted("agent_002", root, a2_plan)},
        agents_root=root, quests_root=quests, rounds=2, seasons=1, name="skillcraft-test")
    res = await world.execute({"board": initial_state(["agent_001", "agent_002"])})
    b = res.context["board"]
    # round 1: a1 posts, a2 searches (no listing yet). round 2: a1 waits, a2 BUYS the listing.
    assert len(b["trade_history"]) == 1, f"expected 1 sale, got {b['trade_history']}"
    assert b["agents"]["agent_002"]["gold"] == 60   # 100 - 40
    assert b["agents"]["agent_001"]["gold"] == 140  # 100 + 40
    assert os.path.isfile(os.path.join(root, "agent_001", "crafted", "recipe_pipeline.md"))
    print(f"  full world: a1 crafted a real .md + posted, a2 bought it (supply chain) — "
          f"gold {b['agents']['agent_001']['gold']}/{b['agents']['agent_002']['gold']} ✓")


def main():
    with tempfile.TemporaryDirectory() as d:
        root = os.path.join(d, "agents"); quests = os.path.join(d, "quests")
        test_guards(root, quests)
        test_advance_bounty()
        asyncio.run(test_full_world(root, quests))
    print("SKILLCRAFT PASS — the real WoS economy, re-assembled from the atoms, faithful to execute.sh")


if __name__ == "__main__":
    main()
