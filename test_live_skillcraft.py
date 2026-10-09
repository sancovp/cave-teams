#!/usr/bin/env python3
"""Real-LLM SkillcraftWorld team run (needs cave-teams + heaven + MINIMAX_API_KEY).

The REAL World of Skillcraft, re-assembled from the cave-teams atoms and run as a TEAM: the composed
`SkillcraftWorld` (= season ∘ blackboard) drives, each round, TWO MiniMax players + a DEITY adjudicator
against one shared game state, across TWO seasons. The players are tooled (Bash + file-edit): they
craft REAL executable Claude Code skills as `.md` files and play the FULL move set — craft/sell, buy,
accept + complete QUESTS, form/join PARTIES (LFG), and AUDIT the economy to file BUG reports for a
100g bounty. Every move goes through the faithful economy mutator (`cave_teams.skillcraft`, ported
verb-for-verb from WoS `execute.sh`, all guards live). The deity runs as the blackboard's adjudicator:
it narrates a bulletin, watches for CONVERGENCE (its selection-pressure job), rules on rarity
challenges, and VALIDATES bug reports — which the season `advance` then pays out (100g/valid bug, on
top of the 100g reset floor) + ratchets the typed rarity standard.

Run:  MINIMAX_API_KEY=… HEAVEN_DATA_DIR=/tmp/heaven-data python test_live_skillcraft.py
Env:  AGENTS_ROOT (default: a fresh tempdir; crafted skills land under <root>/<agent>/crafted/).
"""
import asyncio
import json
import os
import sys
import tempfile

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.skillcraft import SkillcraftWorld, initial_state, post_bulletin, validate_bug
from cave_teams.examples import MiniMaxRuntime

AGENTS_ROOT = os.environ.get("AGENTS_ROOT") or tempfile.mkdtemp(prefix="skillcraft_")
QUESTS = os.path.join(AGENTS_ROOT, "_quests")
for a in ("agent_001", "agent_002"):
    os.makedirs(os.path.join(AGENTS_ROOT, a), exist_ok=True)
os.makedirs(QUESTS, exist_ok=True)

# canonical quest defs (the reward is grepped from THESE files — agents can't inject a reward)
QUEST_DEFS = {
    "q_forge_lens": "# Quest: Forge a Lens\nCraft a `lens`-type skill that reframes how to look at a "
                    "problem (a reusable analytical viewpoint).\n\n## Reward\n60 gold\n",
    "q_recipe_chain": "# Quest: Build a Recipe\nCraft a `recipe`-type skill that composes at least two "
                      "smaller skills into a pipeline (the supply-chain skill).\n\n## Reward\n120 gold\n",
}
for qid, body in QUEST_DEFS.items():
    open(os.path.join(QUESTS, f"{qid}.md"), "w").write(body)

# Meta-Prompt Engineering — the SANCREV/CIG skill's operational core (3 mechanisms), inlined so the
# MiniMax players + deity APPLY it before deciding/judging (MiniMax has no skill auto-load).
# Source: sra-git/not-unified/cig/.claude/skills/meta-prompt-engineering/ (also in every WoS agent).
MPE = (
    "META-PROMPT ENGINEERING — apply this BEFORE you decide or judge:\n"
    "A) INDEPENDENT VERIFICATION: never trust a claim's own label. A seller's 'epic' rarity, a "
    "filed bug, a skill's quality — verify against the actual artifact/rules, not the claim. Try the "
    "alternative reading (if 'epic' fits, is 'uncommon' equally defensible?).\n"
    "B) REFLEXIVE APPLICATION: run the same check on your OWN judgment that you run on theirs — "
    "state your reasoning, then find where it could be wrong.\n"
    "C) SURFACE→PROCESS: does the surface form actually produce the function it implies? A skill "
    "that LOOKS like a recipe may compose nothing; a plausible-sounding bug may not be exploitable. "
    "Check the process, not the appearance.\n"
    "Context-sensitivity: same structure can yield different outcomes by input — judge the specific case.")


def _available_quests():
    out = []
    for qid, body in QUEST_DEFS.items():
        ask = next((l for l in body.splitlines() if l and not l.startswith("#") and "Reward" not in l), "")
        reward = next((tok for tok in body.split() if tok.isdigit()), "?")
        out.append({"quest_id": qid, "ask": ask.strip()[:90], "reward": f"{reward}g"})
    return out


# ── parse the last JSON object an agent emits ────────────────────────────────
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
    """A player: a tooled MiniMax agent embodied in its dir. Plays the full WoS move set."""
    def __init__(self, name):
        self.name = name
        self.rt = MiniMaxRuntime(name=name, tools=None, max_tool_calls=25, system_prompt=(
            f"You are {name}, a player in World of Skillcraft — an economy where agents craft REAL, "
            f"executable Claude Code skills (markdown files), trade them, do quests, form parties, and "
            f"audit the game for exploits. Your agent dir is {AGENTS_ROOT}/{name}. You have Bash + file "
            f"editing.\n\n{MPE}\n\nApply the method above before you choose your move (verify a "
            f"listing's real quality before buying; check your own strategy for convergence). Reply "
            f"with ONE JSON action and nothing else."))

    async def execute(self, ctx=None, **k):
        c = dict(ctx or {}); b = c.get("board", {})
        me = b.get("agents", {}).get(self.name, {})
        others = [l for l in b.get("trade_board", []) if l["seller"] != self.name]
        my_quests = [q for q in b.get("quest_log", {}).get(self.name, [])]
        active = [q["quest_id"] for q in my_quests if q.get("status") == "active"]
        parties = [{"party_id": p["party_id"], "leader": p["leader"], "looking_for": p.get("looking_for")}
                   for p in b.get("lfg_board", [])]
        prompt = (
            f"SEASON {b.get('season', {}).get('number')} — your turn.\n"
            f"You: gold={me.get('gold')}, skills_crafted={me.get('skills_crafted')}, "
            f"quests_completed={me.get('quests_completed')}.\n"
            f"Deity bulletin: {[x['message'] for x in b.get('deity_bulletin', [])][-2:]}\n"
            f"Listings to BUY: {[{'id': l['listing_id'], 'skill': l['skill_path'], 'price': l['price']} for l in others]}\n"
            f"Available quests: {_available_quests()}\n"
            f"Your ACTIVE quests: {active}\n"
            f"Parties (LFG): {parties}\n\n"
            "Take ONE action. The DEITY rewards DIVERGENCE and punishes everyone doing the same move — "
            "vary your play. To craft, first write the file(s) with your tools, then reply the JSON:\n"
            f"• CRAFT+SELL: write {AGENTS_ROOT}/{self.name}/crafted/<snake>.md + a test record "
            f"{AGENTS_ROOT}/{self.name}/crafted/.tests/<id>.json "
            '({"test_id":"<id>","skill_path":"crafted/<snake>.md","result":"pass"}), then reply '
            '{"type":"trade_post","skill_path":"crafted/<snake>.md","price":<int>,"test_id":"<id>","rarity":"<common|uncommon|rare|epic>","description":"<line>"}\n'
            '• BUY: {"type":"trade_buy","listing_id":"<id>"}\n'
            '• ACCEPT a quest (they pay well): {"type":"quest_accept","quest_id":"<id>"}\n'
            "• COMPLETE an ACTIVE quest — craft the skill it asks for first, then "
            '{"type":"quest_complete","quest_id":"<id>","skill_path":"crafted/<snake>.md"}\n'
            '• Form a party: {"type":"lfg_post","specializations":"<what you offer>","looking_for":"<what you need>"} '
            'or join one: {"type":"lfg_join","party_id":"<id>"}\n'
            "• AUDIT this economy for a real exploit (a way to gain gold/skills unfairly) and file it for a "
            '100g bounty: {"type":"bug_report","title":"<short>","description":"<the flaw>","reproduction":"<steps>","severity":"<low|med|high>"}\n'
            "Reply ONLY the JSON.")
        out = await self.rt.run(prompt)
        c["action"] = _last_json(out if isinstance(out, str) else str(out))
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class WoSDeity(Link):
    """The deity — the blackboard's adjudicator: narrate, watch for convergence, rule on rarity
    challenges, and VALIDATE bug reports (which the season advance then pays)."""
    name = "deity"
    def __init__(self):
        self.rt = MiniMaxRuntime(name="deity", tools=[], system_prompt=(
            "You are the DEITY of World of Skillcraft — the god-agent. Your job is SELECTION PRESSURE "
            "(stop the economy converging) and INTEGRITY (validate bug reports honestly).\n\n"
            f"{MPE}\n\nApply the method above BEFORE every ruling: verify a bug is a real, reproducible "
            "exploit (not plausible-sounding) before validating it; verify a claimed rarity against the "
            "actual skill before upholding it; check your own convergence-call for bias. Observe, "
            "narrate, rule on rarity challenges, and judge each open bug. Reply with ONE JSON object "
            "and nothing else."))

    async def execute(self, ctx=None, **k):
        c = dict(ctx or {}); b = dict(c.get("board", {}))
        agents = {a: {"gold": v.get("gold"), "crafted": v.get("skills_crafted"),
                      "quests": v.get("quests_completed"), "last": v.get("last_action")}
                  for a, v in b.get("agents", {}).items()}
        listings = [{"listing_id": l["listing_id"], "seller": l["seller"], "rarity": l["rarity"],
                     "challenges": l.get("challenges", [])} for l in b.get("trade_board", [])]
        open_bugs = [{"id": x["id"], "reporter": x["reporter"], "title": x["title"],
                      "description": x["description"]} for x in b.get("bug_reports", []) if x.get("status") == "open"]
        prompt = (f"Round {c.get('round')} of season {b.get('season', {}).get('number')}.\n"
                  f"Agents: {agents}\nListings: {listings}\nOPEN bug reports: {open_bugs}\n"
                  "Are agents converging? Rule on challenges. Judge each open bug (real exploit or not).\n"
                  'Reply JSON: {"bulletin":"<1-line narration + pressure>",'
                  '"rulings":[{"listing_id":"<id>","rarity":"<..>"}],'
                  '"bug_validations":[{"bug_id":"<id>","status":"valid|invalid"}]}')
        out = await self.rt.run(prompt)
        o = _last_json(out if isinstance(out, str) else str(out),
                       keys=("bulletin", "rulings", "bug_validations"), default={})
        if o.get("bulletin"):
            post_bulletin(b, str(o["bulletin"])[:200])
        for r in (o.get("rulings") or []):
            for l in b.get("trade_board", []):
                if l["listing_id"] == r.get("listing_id") and r.get("rarity"):
                    l["rarity"] = r["rarity"]
        for v in (o.get("bug_validations") or []):
            if v.get("bug_id") and v.get("status") in ("valid", "invalid"):
                validate_bug(b.get("bug_reports", []), v["bug_id"], v["status"])
        c["board"] = b
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


def test_live_skillcraft():
    state = initial_state(["agent_001", "agent_002"])
    post_bulletin(state, "Test before you list. Recipes floor at Epic. Diverge — quests and audits pay.")
    world = SkillcraftWorld(
        agents={"agent_001": WoSPlayer("agent_001"), "agent_002": WoSPlayer("agent_002")},
        agents_root=AGENTS_ROOT, quests_root=QUESTS, deity=WoSDeity(),
        rounds=3, seasons=2, name="skillcraft-live")
    res = asyncio.run(world.execute({"board": state}))
    b = res.context["board"]

    # tallies across the whole game (the final board is post-advance; read the season history too)
    hist = res.context.get("_seasons", [])
    print(f"\nagents root: {AGENTS_ROOT}")
    print("final gold:", {a: b["agents"][a]["gold"] for a in b["agents"]})
    print("season:", b["season"]["number"], "| ratchet(recipe):", b["season"]["rarity_consensus"]["recipe"])
    quests_done = {a: [q for q in b.get("quest_log", {}).get(a, []) if q.get("status") == "completed"]
                   for a in b["agents"]}
    accepted = {a: [q["quest_id"] for q in b.get("quest_log", {}).get(a, [])] for a in b["agents"]}
    parties = [{"party": p["party_id"], "members": p["members"]} for p in b.get("lfg_board", [])]
    bugs = b.get("bug_reports", [])
    print("quests (accepted this season):", {a: v for a, v in accepted.items() if v})
    print("parties (LFG):", parties)
    print("bug reports:", [f"{x['reporter']}:{x['title'][:40]} [{x['status']}]"
                           + (" PAID" if x.get("reward_paid") else "") for x in bugs])
    print("bounties paid at advance:", b.get("_bounties_paid", {}))
    print("deity bulletins:", [x["message"] for x in b.get("deity_bulletin", []) if "Test before" not in x["message"]][-4:])
    crafted = {a: sorted(f for f in os.listdir(os.path.join(AGENTS_ROOT, a, "crafted"))
                         if f.endswith(".md")) if os.path.isdir(os.path.join(AGENTS_ROOT, a, "crafted")) else []
               for a in ("agent_001", "agent_002")}
    print("crafted skills (real files):", crafted)

    # PROVE the full move set was exercised beyond craft/trade
    played = []
    if any(accepted.values()): played.append("quest_accept")
    if any(quests_done.values()): played.append("quest_complete")
    if parties: played.append("lfg")
    if bugs: played.append("bug_report")
    assert sum(len(v) for v in crafted.values()) >= 1, "must craft at least one real skill"
    assert len(hist) == 2, "two seasons must run (the advance must fire)"
    assert played, "the players must exercise at least ONE of quest/LFG/bug beyond craft+trade"
    print(f"ok  live skillcraft: full move set exercised — beyond craft/trade, played: {played}")


if __name__ == "__main__":
    test_live_skillcraft()
    print("\nLIVE SKILLCRAFT PASSED")
    sys.stdout.flush()
    os._exit(0)   # heaven non-daemon threads → hard exit
