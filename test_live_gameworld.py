"""Real-LLM gameworld run (needs cave + heaven + MINIMAX_API_KEY): GameWorld/season/blackboard
driven by ACTUAL MiniMax agents — the live coverage the scripted smokes don't give.

First live run (2026-07-03) verified: skill COMPOSITION emerged (a player chained each crafted
skill on its previous one), the market opened (a real listing), the deity adjudicated externally
(xp awards + a bulletin narrating the economy), and the season boundary carried skills/xp, reset
gold, and RATCHETED craft_cost. Engine findings from that run, kept honest here:
  - Season.execute drops the arena's _blackboard_log at each boundary (board snapshots survive;
    the play-by-play doesn't) — so this test asserts on the BOARD, not the log.
  - BaseHeavenAgent restores the persisted per-agent_id skillset (skill_manager) on every run —
    world agents inherit the HOST skillset unless a persona/skillset is set for them. Isolation
    of the equip is heaven-persona work, not cave-teams work.
"""
import asyncio
import json

from cave_teams.chain_ontology import Link, LinkResult, LinkStatus
from cave_teams.gameworld import GameWorld
from cave_teams.season import carry_reset_ratchet
from cave_teams.examples import MiniMaxRuntime


def _jobj(text):
    """Last balanced top-level JSON object in text (string-aware) — mirrors runner._json_objects."""
    spans, depth, start, in_s, esc = [], 0, -1, False, False
    for i, ch in enumerate(text or ""):
        if in_s:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_s = False
            continue
        if ch == '"' and depth > 0:
            in_s = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                spans.append(text[start:i + 1])
    for blob in reversed(spans):
        try:
            o = json.loads(blob)
            if isinstance(o, dict):
                return o
        except Exception:
            continue
    return None


async def _call_rt(rt, prompt):
    """Mirror links.AgentLink: await async .run, thread sync .run."""
    if asyncio.iscoroutinefunction(rt.run):
        res = await rt.run(prompt)
    else:
        res = await asyncio.to_thread(rt.run, prompt)
    if asyncio.iscoroutine(res):
        res = await res
    return res


class _Player(Link):
    def __init__(self, name):
        self.name = name
        self.rt = MiniMaxRuntime(name=name, tools=[], system_prompt=(
            f"You are {name}, a player in a skill-crafting game. You act to maximize gold+xp. "
            "Reply with ONE JSON action object and nothing else."))

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        b = ctx.get("board", {})
        me = b.get("agents", {}).get(self.name, {})
        prompt = (
            f"BOARD season={ctx.get('season')} round={ctx.get('round')}:\n"
            f"  you: gold={me.get('gold', 0)} xp={me.get('xp', 0)} skills={me.get('skills', [])}\n"
            f"  market (skills for sale): {json.dumps(b.get('market', []))}\n"
            f"  craft cost this season: {b.get('craft_cost', 10)} gold\n"
            f"  bulletin: {b.get('bulletin', '(none)')}\n"
            "ACTIONS (pick ONE):\n"
            '  {"type":"craft","skill":"<snake_case_name>","desc":"<what it does, 1 line>"}  (costs craft_cost)\n'
            '  {"type":"sell","skill":"<one you own>","price":<gold int>}\n'
            '  {"type":"buy","skill":"<market skill>","from":"<seller>"}\n'
            "Composing/crafting novel skills that combine existing ones earns deity XP.")
        out = await _call_rt(self.rt, prompt)
        ctx["action"] = _jobj(out if isinstance(out, str) else str(out))
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)


class _Deity(Link):
    name = "deity"

    def __init__(self):
        self.rt = MiniMaxRuntime(name="deity", tools=[], system_prompt=(
            "You are the DEITY adjudicating a skill-crafting game. Judge novelty/composition "
            "EXTERNALLY (market activity counts more than self-claims). Reply ONE JSON object: "
            '{"bulletin":"<1 line to all players>","xp_awards":{"<player>":<int>}}'))

    async def execute(self, context=None, **k):
        ctx = dict(context) if context else {}
        b = dict(ctx.get("board", {}))
        out = await _call_rt(
            self.rt, f"BOARD round={ctx.get('round')}: {json.dumps(b, default=str)[:2000]}\nJudge it.")
        o = _jobj(out if isinstance(out, str) else str(out)) or {}
        b["bulletin"] = str(o.get("bulletin", ""))[:200]
        ag = dict(b.get("agents", {}))
        for p, xp in (o.get("xp_awards") or {}).items():
            if p in ag and isinstance(xp, (int, float)):
                a = dict(ag[p])
                a["xp"] = a.get("xp", 0) + int(xp)
                ag[p] = a
        b["agents"] = ag
        ctx["board"] = b
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)


def _econ(state, agent, action):
    """The world's physics: craft (spend), sell (list), buy (transfer gold + copy skill;
    a completed sale pays the seller xp — market-priced = external valuation, LAWS P2)."""
    if not isinstance(action, dict):
        raise ValueError(f"non-dict action: {action!r}")
    s = dict(state)
    ag = dict(s.get("agents", {}))
    me = dict(ag.get(agent, {"gold": 20, "xp": 0, "skills": []}))
    market = list(s.get("market", []))
    cost = s.get("craft_cost", 10)
    t = action.get("type")
    if t == "craft":
        name = str(action.get("skill", "")).strip()
        if not name:
            raise ValueError("craft: no skill name")
        if me.get("gold", 0) < cost:
            raise ValueError(f"craft: needs {cost} gold, has {me.get('gold', 0)}")
        me["gold"] -= cost
        me["skills"] = list(me.get("skills", [])) + [
            {"name": name, "desc": str(action.get("desc", ""))[:120]}]
    elif t == "sell":
        name = str(action.get("skill", ""))
        if name not in [x["name"] for x in me.get("skills", [])]:
            raise ValueError(f"sell: {agent} doesn't own {name}")
        market.append({"skill": name, "seller": agent, "price": max(1, int(action.get("price", 5)))})
    elif t == "buy":
        name = str(action.get("skill", ""))
        seller = str(action.get("from", ""))
        lot = next((m for m in market if m["skill"] == name and m["seller"] == seller), None)
        if lot is None:
            raise ValueError(f"buy: no listing {name} by {seller}")
        if me.get("gold", 0) < lot["price"]:
            raise ValueError("buy: insufficient gold")
        sl = dict(ag.get(seller, {"gold": 20, "xp": 0, "skills": []}))
        src = next((x for x in sl.get("skills", []) if x["name"] == name), {"name": name, "desc": ""})
        me["gold"] -= lot["price"]
        sl["gold"] = sl.get("gold", 0) + lot["price"]
        sl["xp"] = sl.get("xp", 0) + 2
        me["skills"] = list(me.get("skills", [])) + [dict(src)]
        market.remove(lot)
        ag[seller] = sl
    else:
        raise ValueError(f"unknown action type: {t}")
    ag[agent] = me
    s["agents"] = ag
    s["market"] = market
    return s


def test_live_gameworld():
    world = GameWorld(
        {"ada": _Player("ada"), "bo": _Player("bo")}, _econ, deity=_Deity(),
        advance=carry_reset_ratchet(
            reset_to={"market": lambda: []},
            ratchet=lambda b, n: {**b,
                                  "craft_cost": b.get("craft_cost", 10) + 5,
                                  "agents": {p: {**a, "gold": 20}
                                             for p, a in b.get("agents", {}).items()}}),
        rounds=2, seasons=2, name="live-micro-wos")
    board0 = {"agents": {"ada": {"gold": 20, "xp": 0, "skills": []},
                         "bo": {"gold": 20, "xp": 0, "skills": []}},
              "market": [], "craft_cost": 10}
    r = asyncio.run(world.execute({"board": board0}))
    out = r.context or {}
    board = out.get("board", {})
    seasons = out.get("_seasons", [])

    print(json.dumps(board, indent=2, default=str)[:1500])
    for s in seasons:
        b = s["board"]
        print(f"season {s['season']}: craft_cost={b.get('craft_cost')} " +
              " ".join(f"{p}:g{a.get('gold')} xp{a.get('xp')} sk{len(a.get('skills', []))}"
                       for p, a in b.get("agents", {}).items()))

    assert len(seasons) == 2, "two seasons must run"
    assert board.get("craft_cost", 0) > 10, "the ratchet must tighten the standard"
    crafted = sum(len(a.get("skills", [])) for a in board.get("agents", {}).values())
    assert crafted > 0, "real agents must have crafted at least one skill"
    s1 = seasons[0]["board"]
    carried = all(
        len(board["agents"][p].get("skills", [])) >= len(a.get("skills", []))
        for p, a in s1.get("agents", {}).items())
    assert carried, "skills must CARRY across the season boundary"
    print("ok  live gameworld: craft/market/deity/season all exercised by real agents")


if __name__ == "__main__":
    test_live_gameworld()
    print("\nLIVE GAMEWORLD PASSED")
