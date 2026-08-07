#!/usr/bin/env python3
"""Real-LLM SkillcraftWorld team run (needs cave-teams + heaven + MINIMAX_API_KEY).

The REAL World of Skillcraft, re-assembled from the cave-teams atoms and run as a TEAM: the composed
`SkillcraftWorld` (= season ∘ blackboard) drives, each round, TWO MiniMax players + a DEITY adjudicator
against one shared game state. The players are tooled (Bash + file-edit) — they craft REAL executable
Claude Code skills as `.md` files on disk and trade them; every move goes through the faithful economy
mutator (`cave_teams.skillcraft`, ported verb-for-verb from WoS `execute.sh`, all guards live). The
deity runs as the blackboard's adjudicator: it narrates a bulletin, watches for agent CONVERGENCE (its
real selection-pressure job), and rules on rarity challenges.

First live run (2026-08-07): the two players crafted real skills and closed a real sale (gold moved
atomically through the mutator); the deity posted bulletins that read the economy on their own
("agent_002 bought high vs agent_001's sell — price inefficiency exists") and watched for convergence.

Run:  MINIMAX_API_KEY=… HEAVEN_DATA_DIR=/tmp/heaven-data python test_live_skillcraft.py
Env:  AGENTS_ROOT (default: a fresh tempdir; crafted skills land under <root>/<agent>/crafted/).
"""
import asyncio
import json
import os
import sys
import tempfile

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.skillcraft import SkillcraftWorld, initial_state, post_bulletin
from cave_teams.examples import MiniMaxRuntime

AGENTS_ROOT = os.environ.get("AGENTS_ROOT") or tempfile.mkdtemp(prefix="skillcraft_")
QUESTS = os.path.join(AGENTS_ROOT, "_quests")
for a in ("agent_001", "agent_002"):
    os.makedirs(os.path.join(AGENTS_ROOT, a), exist_ok=True)
os.makedirs(QUESTS, exist_ok=True)


# ── parse the last JSON object an agent emits (players → type/action; deity → bulletin/rulings) ──
def _spans(text):
    depth = start = 0; in_s = esc = False; out = []
    for i, ch in enumerate(text or ""):
        if in_s:
            esc = (ch == "\\" and not esc)
            if ch == '"' and not esc: in_s = False
            continue
        if ch == '"': in_s = True
        elif ch == "{":
            if depth == 0: start = i
            depth += 1
        elif ch == "}" and depth:
            depth -= 1
            if depth == 0: out.append(text[start:i + 1])
    return out

def _last_json(text, keys=("type", "action"), default=None):
    for blob in reversed(_spans(text)):
        try:
            o = json.loads(blob)
            if isinstance(o, dict) and any(k in o for k in keys):
                return o.get("action", o) if "action" in o else o
        except Exception:
            continue
    return default if default is not None else {"type": "search"}


# ── the two team roles ────────────────────────────────────────────────────────
class WoSPlayer(Link):
    """A player: a tooled MiniMax agent embodied in its dir. Reads the world, crafts a real skill
    file + a test record, and emits a WoS action (trade_post / trade_buy)."""
    def __init__(self, name):
        self.name = name
        self.rt = MiniMaxRuntime(name=name, tools=None, max_tool_calls=25, system_prompt=(
            f"You are {name}, a player in World of Skillcraft — an economy where agents craft REAL, "
            f"executable Claude Code skills (markdown files) and trade them for gold. Your agent dir is "
            f"{AGENTS_ROOT}/{name}. You have Bash + file editing. Reply with ONE JSON action and nothing else."))

    async def execute(self, ctx=None, **k):
        c = dict(ctx or {}); b = c.get("board", {})
        me = b.get("agents", {}).get(self.name, {})
        others = [l for l in b.get("trade_board", []) if l["seller"] != self.name]
        prompt = (
            f"SEASON {b.get('season', {}).get('number')} — your turn.\n"
            f"You: gold={me.get('gold')}, skills_crafted={me.get('skills_crafted')}.\n"
            f"Deity bulletin: {[x['message'] for x in b.get('deity_bulletin', [])]}\n"
            f"Listings you could BUY: {[{'listing_id': l['listing_id'], 'skill': l['skill_path'], 'price': l['price'], 'rarity': l['rarity']} for l in others]}\n\n"
            "Take ONE action:\n"
            f"• CRAFT+SELL: (1) write a genuinely useful skill to {AGENTS_ROOT}/{self.name}/crafted/<snake>.md "
            f"(real capability, not a stub); (2) write {AGENTS_ROOT}/{self.name}/crafted/.tests/<test_id>.json = "
            '{"test_id":"<id>","skill_path":"crafted/<snake>.md","result":"pass"}; (3) reply '
            '{"type":"trade_post","skill_path":"crafted/<snake>.md","price":<int>,"test_id":"<id>","rarity":"<common|uncommon|rare|epic>","description":"<line>"}\n'
            '• BUY a listing you can afford: reply {"type":"trade_buy","listing_id":"<id>"}\n'
            "Do the file writes with your tools BEFORE replying. Reply ONLY the JSON.")
        out = await self.rt.run(prompt)
        c["action"] = _last_json(out if isinstance(out, str) else str(out))
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class WoSDeity(Link):
    """The deity — the blackboard's adjudicator. Each round: narrate a bulletin, watch for convergence
    (the selection-pressure job), rule on rarity challenges. Reasons only; its rulings mutate the board."""
    name = "deity"
    def __init__(self):
        self.rt = MiniMaxRuntime(name="deity", tools=[], system_prompt=(
            "You are the DEITY of World of Skillcraft — the god-agent. Your job is SELECTION PRESSURE: "
            "keep the economy from converging (all agents doing the same thing). Observe, narrate a "
            "bulletin, and rule on rarity challenges. Reply with ONE JSON object and nothing else."))

    async def execute(self, ctx=None, **k):
        c = dict(ctx or {}); b = dict(c.get("board", {}))
        agents = {a: {"gold": v.get("gold"), "crafted": v.get("skills_crafted"),
                      "trades": v.get("trades_completed"), "last": v.get("last_action")}
                  for a, v in b.get("agents", {}).items()}
        listings = [{"listing_id": l["listing_id"], "seller": l["seller"], "rarity": l["rarity"],
                     "price": l["price"], "challenges": l.get("challenges", [])} for l in b.get("trade_board", [])]
        prompt = (f"Round {c.get('round')} of season {b.get('season', {}).get('number')}.\n"
                  f"Agents: {agents}\nListings: {listings}\n"
                  "Are agents converging (same actions/strategy)? Rule on any challenged listings.\n"
                  'Reply JSON: {"bulletin":"<1-line deity narration + any rule/pressure>",'
                  '"rulings":[{"listing_id":"<id>","rarity":"<common|uncommon|rare|epic>"}]}')
        out = await self.rt.run(prompt)
        o = _last_json(out if isinstance(out, str) else str(out), keys=("bulletin", "rulings"), default={})
        if o.get("bulletin"):
            post_bulletin(b, str(o["bulletin"])[:200])
        for r in (o.get("rulings") or []):
            for l in b.get("trade_board", []):
                if l["listing_id"] == r.get("listing_id") and r.get("rarity"):
                    l["rarity"] = r["rarity"]                 # the deity's ruling overrides the claim
        c["board"] = b
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


def test_live_skillcraft():
    state = initial_state(["agent_001", "agent_002"])
    post_bulletin(state, "Test before you list. Recipes floor at Epic. Compose, don't just template.")
    world = SkillcraftWorld(
        agents={"agent_001": WoSPlayer("agent_001"), "agent_002": WoSPlayer("agent_002")},
        agents_root=AGENTS_ROOT, quests_root=QUESTS, deity=WoSDeity(),
        rounds=2, seasons=1, name="skillcraft-live")
    res = asyncio.run(world.execute({"board": state}))
    b = res.context["board"]

    print(f"\nagents root: {AGENTS_ROOT}")
    print("gold:", {a: b["agents"][a]["gold"] for a in b["agents"]})
    print("trade_board:", [f"{l['seller']} {l['skill_path']} [{l['rarity']}] {l['price']}g" for l in b["trade_board"]])
    print("trade_history:", [f"{h['buyer']}<-{h['seller']} {h['skill_path']} {h['price']}g" for h in b["trade_history"]])
    print("deity bulletins:", [x["message"] for x in b.get("deity_bulletin", []) if "Test before" not in x["message"]])
    crafted = {a: [f for f in os.listdir(os.path.join(AGENTS_ROOT, a, "crafted"))
                   if f.endswith(".md")] if os.path.isdir(os.path.join(AGENTS_ROOT, a, "crafted")) else []
               for a in ("agent_001", "agent_002")}
    print("crafted skills (real files):", crafted)

    total_crafted = sum(len(v) for v in crafted.values())
    assert total_crafted >= 1, "players must craft at least one real skill file"
    assert (len(b["trade_board"]) + len(b["trade_history"])) >= 1, "at least one listing or sale must exist"
    # the deity bulletins beyond the seeded rule = it actually adjudicated
    deity_msgs = [x for x in b.get("deity_bulletin", []) if "Test before" not in x["message"]]
    assert deity_msgs, "the deity must post at least one bulletin (it ran as adjudicator)"
    print("ok  live skillcraft: real skills crafted + traded through the faithful economy; deity adjudicated")


if __name__ == "__main__":
    test_live_skillcraft()
    print("\nLIVE SKILLCRAFT PASSED")
    sys.stdout.flush()
    os._exit(0)   # heaven non-daemon threads → hard exit
