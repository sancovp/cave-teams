#!/usr/bin/env python3
"""AgentDir — the devdir as a class, deterministic (NO API). The completion of
the WoS port: the agent's BODY (the real vendored `agents/_template` with its
.claude loadout), built/equipped/embodied/harvested through one type, and the
proof that bodies + worlds compose (a SkillcraftWorld round played by agents
with real template bodies; the trade lands in the buyer's bought/)."""
import asyncio
import tempfile
from pathlib import Path

from cave_teams.agentdir import AgentDir, scaffold_agents, DEFAULT_TEMPLATE
from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.skillcraft import (SkillcraftWorld, initial_state,
                                   craft_skill, record_test)


def test_body_from_template(root):
    a = AgentDir.from_template(root, "agent_007")
    # the identity is rendered (the original {{AGENT_ID}} rule)
    ident = a.identity()
    assert "{{AGENT_ID}}" not in ident and "agent_007" in ident
    # the REAL loadout came with the body (the vendored WoS template)
    skills = a.skills()
    for expected in ("execute_in_game", "test_skill", "bug_report", "places"):
        assert expected in skills, f"missing template skill: {expected}"
    assert (a.path / ".claude" / "skills" / "test_skill" / "test.sh").is_file()
    assert (a.path / "crafted").is_dir() and (a.path / "bought").is_dir()
    # no duplicate bodies
    try:
        AgentDir.from_template(root, "agent_007")
        raise AssertionError("duplicate body must refuse")
    except FileExistsError:
        pass
    print(f"  body: template stamped + rendered, loadout {len(skills)} skills "
          f"(incl. execute_in_game/test_skill), refusal on duplicate ✓")


def test_equip_and_harvest(root):
    a = AgentDir.existing(Path(root) / "agent_007")
    a.equip_skill("golden_thing", "# golden\nshipped by the factory")
    a.equip_rule("no_skip", "never skip the gate")
    assert "golden_thing" in a.skills()
    assert (a.path / ".claude" / "rules" / "no_skip.md").is_file()
    sp = craft_skill(root, "agent_007", "my_craft", "# crafted by me")
    record_test(root, "agent_007", sp, "pass")
    assert [p.name for p in a.crafted()] == ["my_craft.md"]
    assert a.tests()[0]["skill_path"] == "crafted/my_craft.md"
    print("  equip (.claude/skills + .claude/rules) + harvest "
          "(crafted/tests) ✓")


def test_embody_socket(root):
    a = AgentDir.existing(Path(root) / "agent_007")

    class HeavenLike:                      # carries working_dir (heaven-style)
        working_dir = None

    class Bare:                            # carries nothing
        pass

    h = a.embody(HeavenLike())
    assert h.working_dir == str(a.path) and h.agent_dir == str(a.path)
    b = a.rehydrate(Bare())
    assert b.agent_dir == str(a.path)      # the dir travels with the runtime
    print("  embodiment socket: working_dir/cwd set when carried; agent_dir "
          "always attached; rehydrate = give the dir to a fresh process ✓")


class _Seller(Link):
    def __init__(self, name, root):
        self.name, self.root, self._done = name, root, False

    async def execute(self, ctx=None, **_):
        c = dict(ctx or {})
        if not self._done:
            self._done = True
            sp = craft_skill(self.root, self.name, "wares", "# real wares")
            tid = record_test(self.root, self.name, sp, "pass")
            c["action"] = {"type": "trade_post", "skill_path": sp, "price": 30,
                           "test_id": tid, "rarity": "common",
                           "description": "wares"}
        else:
            c["action"] = {"type": "wait"}
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class _Buyer(Link):
    def __init__(self, name):
        self.name = name

    async def execute(self, ctx=None, **_):
        c = dict(ctx or {})
        ls = c.get("board", {}).get("trade_board", [])
        c["action"] = ({"type": "trade_buy", "listing_id": ls[0]["listing_id"]}
                       if ls else {"type": "search"})
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


def test_bodies_plus_world(root):
    """scaffold_agents replaces the hand-written _seed_world glue: real
    template bodies play a SkillcraftWorld round; the purchase lands in the
    buyer's body (bought/<seller>/ — trade.sh:198 through the world)."""
    bodies = scaffold_agents(root, ["seller_1", "buyer_1"])
    quests = str(Path(root) / "_quests")
    Path(quests).mkdir()
    world = SkillcraftWorld(
        agents={"seller_1": _Seller("seller_1", root), "buyer_1": _Buyer("buyer_1")},
        agents_root=root, quests_root=quests, rounds=2, seasons=1,
        name="bodies+world")
    res = asyncio.run(world.execute(
        {"board": initial_state(["seller_1", "buyer_1"])}))
    b = res.context["board"]
    assert len(b["trade_history"]) == 1
    got = bodies["buyer_1"].bought()
    assert "seller_1" in got and got["seller_1"][0].name == "wares.md"
    assert "execute_in_game" in bodies["buyer_1"].skills()   # body intact
    print("  bodies + world: scaffolded template agents played a round; the "
          "purchase landed in the buyer's bought/ ✓")


def main():
    with tempfile.TemporaryDirectory() as d:
        test_body_from_template(d)
        test_equip_and_harvest(d)
        test_embody_socket(d)
    with tempfile.TemporaryDirectory() as d:
        test_bodies_plus_world(d)
    print("AGENTDIR PASS — the devdir is a class: the real WoS template body, "
          "equip/embody/rehydrate/harvest as signatures, and worlds compose "
          "with bodies. The WoS port now includes the operating environment.")


if __name__ == "__main__":
    main()
