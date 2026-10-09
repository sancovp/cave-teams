#!/usr/bin/env python3
"""GauntletWorld smoke — the viral Gauntlet Loop as one preset, with the four deltas the
prompt version cannot express PROVEN deterministically (no keys, no network):
  1. the ownership contract is ENFORCED (a rogue cross-subsystem write is rejected; the
     arena survives; the victim subsystem is never corrupted; the rogue pays in progress)
  2. the critique ledger CARRIES across the season boundary (fresh-context critics forget;
     ours accretes)
  3. the bar RATCHETS at each boundary (termination is in-world, not an operator's patience)
  4. the run is RE-ENTRANT (the final board resumes a second run — the session-shaped loop
     cannot be re-entered at all)

Found-by-this-test (kept as living notes):
  - the blackboard's `_blackboard_log` is not surfaced through Season's final context —
    rejections must be asserted via board effects (observability gap for streaming/audit).
  - a critic that sets board["_stop"] must CLEAR it on later verdicts, or the stale flag
    ends every subsequent season after one round.
"""
import asyncio

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.gauntlet import GauntletWorld


class Builder(Link):
    """A subsystem builder: improves its build each round; the rogue one tries a
    cross-subsystem write on round 0 of every season (the contract must catch each)."""
    def __init__(self, name, rogue=False):
        self.name = name
        self.rogue = rogue

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        board = ctx.get("board", {})
        prev = (board.get("subsystems", {}) or {}).get(self.name)
        quality = (prev or {}).get("quality", 0) + 1
        target = "render" if (self.rogue and ctx.get("round") == 0 and self.name != "render") else self.name
        ctx["action"] = {"subsystem": target, "build": {"quality": quality, "by": self.name}}
        return LinkResult(LinkStatus.SUCCESS, ctx)


class BlindCritic(Link):
    """The adjudicator: compares total build quality to the bar, appends an ordinal verdict
    to the CARRIED critique ledger, stops the season when the pick flips to candidate.
    Clears any stale _stop first — a verdict is per-observation, never inherited."""
    def __init__(self):
        self.name = "critic"

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        board = dict(ctx.get("board", {}))
        board.pop("_stop", None)
        total = sum((b or {}).get("quality", 0) for b in board.get("subsystems", {}).values())
        pick = "candidate" if total >= board.get("bar", 1) * 10 else "reference"
        ledger = list(board.get("critique", []))
        ledger.append({"round": ctx.get("round"), "season": ctx.get("season"),
                       "total": total, "bar": board.get("bar", 1), "pick": pick})
        board["critique"] = ledger
        if pick == "candidate":
            board["_stop"] = True            # the bar was BEATEN this season — in-world stop
        ctx["board"] = board
        return LinkResult(LinkStatus.SUCCESS, ctx)


async def main():
    builders = {"render": Builder("render"), "audio": Builder("audio", rogue=True),
                "ai": Builder("ai")}

    world = GauntletWorld(builders, critic=BlindCritic(), rounds=4, seasons=3)
    r = await world.execute({"board": {"bar": 1}})
    board = r.context["board"]
    subs = board["subsystems"]

    # 1. the ownership contract fired every season: the rogue's cross-writes were rejected,
    #    render was never corrupted (only render ever wrote it), the arena survived, and
    #    audio paid one lost increment per season relative to the clean builders
    assert subs["render"]["by"] == "render", f"render corrupted by {subs['render']['by']}"
    assert subs["render"]["quality"] == subs["ai"]["quality"]        # clean builders identical
    lost = subs["render"]["quality"] - subs["audio"]["quality"]
    assert lost == len(r.context["_seasons"]), f"expected 1 rejection/season, lost={lost}"

    # 2. the critique ledger carried across season boundaries (entries from >1 season)
    ledger_seasons = {e["season"] for e in board["critique"]}
    assert len(ledger_seasons) >= 2, f"ledger did not carry: {ledger_seasons}"

    # 3. the bar ratcheted at each boundary
    assert board["bar"] == 3, f"bar did not ratchet: {board['bar']}"

    # 4. RE-ENTRY: resume the finished world's board in a NEW run — quality and ledger continue
    prev_len = len(board["critique"])
    prev_q = subs["render"]["quality"]
    board2_in = {k: v for k, v in board.items() if k != "_stop"}
    r2 = await GauntletWorld(builders, critic=BlindCritic(), rounds=2, seasons=1).execute(
        {"board": board2_in})
    b2 = r2.context["board"]
    assert b2["subsystems"]["render"]["quality"] > prev_q
    assert len(b2["critique"]) > prev_len

    print("GAUNTLET SMOKE PASS")
    print(f"  seasons run: {len(r.context['_seasons'])}, bar ratcheted to {board['bar']}")
    print(f"  contract: render untouched by rogue; audio lost {lost} increments to rejections")
    print(f"  critique ledger: {prev_len} entries across seasons {sorted(ledger_seasons)}")
    print(f"  re-entered run: render quality {prev_q} -> {b2['subsystems']['render']['quality']}, "
          f"ledger {prev_len} -> {len(b2['critique'])}")


if __name__ == "__main__":
    asyncio.run(main())
