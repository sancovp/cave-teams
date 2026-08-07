"""
worlds_test.py — test each cave-teams WORLD FEATURE individually (Isaac's goal: test each world
feature; skip the complex WoS/gameworld composition). Real MiniMax agents where the feature runs
agents; deterministic where the feature is file ops. Reads the resulting STATE, not a pass flag.

Features covered: blackboard (arena) · metacog (reflection) · season (multi-epoch) · evolve
(reproduction: inherit dir, wipe memory) + select_winners. sim/gameworld/npc = the WoS composition
(tournament+select+evolve over real crafter dirs) — deferred per Isaac; its parts are each verified.
"""
import os, sys, json, asyncio, time

sys.path.insert(0, os.path.expanduser("~/repo/cave-teams"))
from cave_teams import AgentLink, blackboard, metacog_shell, season
from cave_teams.season import carry_reset_ratchet
from cave_teams.evolve import evolve_dir, evolve, select_winners
from cave_teams.chain_ontology import Link, LinkResult, LinkStatus

SD = os.path.dirname(os.path.abspath(__file__))
T0 = time.time()
def log(m): print(f"[{time.time()-T0:6.1f}s] {m}", flush=True)


class AsKey(Link):
    """Run a real AgentLink, expose its text output under a specific ctx key the world feature reads
    (blackboard wants ctx['action']; metacog wants 'work'/'extracted_skills'/'assessment')."""
    def __init__(self, name, agent, key, as_list=False):
        self.name = name; self._a = agent; self._k = key; self._list = as_list
    async def execute(self, ctx=None, **kw):
        r = await self._a.execute(dict(ctx or {}))
        out = (r.context or {}).get("output", "")
        c = dict(r.context or ctx or {})
        c[self._k] = [out] if self._list else out
        return LinkResult(status=LinkStatus.SUCCESS, context=c)

def A(name, sp): return AgentLink(name, system_prompt=sp, backend="minimax")


# ── blackboard ────────────────────────────────────────────────────────────
async def test_blackboard():
    log("BLACKBOARD: 2 agents ↔ shared board ↔ mutator, 2 rounds")
    agents = {
        "optimist": AsKey("optimist", A("optimist", "In ONE short line, state a BENEFIT of remote "
                          "work. If the board already has entries, add a NEW distinct one."), "action"),
        "skeptic":  AsKey("skeptic", A("skeptic", "In ONE short line, state a RISK of remote work. "
                          "If the board already has entries, add a NEW distinct one."), "action"),
    }
    def mutator(state, name, action):
        s = dict(state)
        s[name] = action.strip()[:120]
        s["_moves"] = s.get("_moves", []) + [name]
        return s
    arena = blackboard(agents, mutator, rounds=2)
    res = await arena.execute({"board": {}})
    board = res.context["board"]
    log_ = res.context["_blackboard_log"]
    ok = "optimist" in board and "skeptic" in board and len([m for m in log_ if m["ok"]]) == 4
    print("  FINAL BOARD:", {k: v for k, v in board.items() if not k.startswith("_")})
    print("  moves (2 rounds × 2 agents):", board.get("_moves"))
    print("  applied writes:", [f"{m['agent']}:{m['ok']}" for m in log_])
    return ("blackboard", ok, {"board_keys": list(board), "n_writes": len(log_)})


# ── metacog ───────────────────────────────────────────────────────────────
async def test_metacog():
    log("METACOG: executor → observer(extract skill) → meta(assess), 1 cycle")
    executor = AsKey("exec", A("exec", "You are given a task. Do it in 2 sentences."), "work")
    observer = AsKey("obs", A("obs", "You are given a piece of work. Name ONE reusable SKILL it "
                     "demonstrates, in 3 words."), "extracted_skills", as_list=True)
    meta     = AsKey("meta", A("meta", "You are given work + an extracted skill. In one sentence, "
                     "assess the METHODOLOGY and how to improve it."), "assessment")
    shell = metacog_shell(executor, observer, meta, cycles=1)
    res = await shell.execute({"task": "Summarize why unit tests matter, for a junior dev."})
    cyc = res.context["_cycles"][0]
    ok = bool(cyc.get("work")) and bool(cyc.get("extracted")) and bool(cyc.get("meta_assessment"))
    print("  work:", str(cyc.get("work"))[:120])
    print("  extracted_skills:", cyc.get("extracted"))
    print("  meta_assessment:", str(cyc.get("meta_assessment"))[:160])
    return ("metacog", ok, {"skills_accumulated": res.context.get("skills")})


# ── season ────────────────────────────────────────────────────────────────
async def test_season():
    log("SEASON: a blackboard arena over 2 seasons; carry earned state, reset the transient 'scratch'")
    agents = {
        "player": AsKey("player", A("player", "Add ONE short achievement to your record for this "
                        "season. If a record exists, extend it."), "action"),
    }
    def mutator(state, name, action):
        s = dict(state)
        s["record"] = (s.get("record", "") + " | " + action.strip()[:60]).strip(" |")  # EARNED (carries)
        s["scratch"] = action.strip()[:40]                                              # TRANSIENT (resets)
        return s
    arena = blackboard(agents, mutator, rounds=1)
    advance = carry_reset_ratchet(reset_to={"scratch": ""})   # scratch resets each season; record carries
    seas = season(arena, advance=advance, seasons=2)
    res = await seas.execute({"board": {}})
    hist = res.context["_seasons"]
    final = res.context["board"]
    # earned 'record' should carry across both seasons (contain 2 entries); scratch reset at boundary
    carried = final.get("record", "").count("|") >= 1
    ok = len(hist) == 2 and carried
    print("  season snapshots:", [{k: str(v)[:40] for k, v in h["board"].items() if not k.startswith('_')} for h in hist])
    print("  FINAL record (carried across seasons):", final.get("record"))
    return ("season", ok, {"seasons": len(hist), "final_record": final.get("record")})


# ── evolve (deterministic — reproduction: inherit architecture, wipe memory) ──
def test_evolve():
    log("EVOLVE: copy a winner's whole AIOS dir → child, wipe session memory (architecture inherited)")
    base = os.path.join(SD, "EVOLVE_TEST")
    os.system(f"rm -rf {base}")
    win = os.path.join(base, "winner")
    os.makedirs(os.path.join(win, ".claude", "skills", "craft"), exist_ok=True)
    open(os.path.join(win, "CLAUDE.md"), "w").write("# Winner AIOS\nthe evolved architecture")
    open(os.path.join(win, ".claude", "skills", "craft", "SKILL.md"), "w").write("emergent skill")
    open(os.path.join(win, "short_term_memory.jsonl"), "w").write('{"session":"parent memory"}')
    child = evolve_dir(win, os.path.join(base, "child"))
    inherited_claude = os.path.isfile(os.path.join(child, "CLAUDE.md"))
    inherited_skill = os.path.isfile(os.path.join(child, ".claude", "skills", "craft", "SKILL.md"))
    memory_wiped = not os.path.isfile(os.path.join(child, "short_term_memory.jsonl"))
    winners = select_winners([("dirA", 0.2), ("dirB", 0.9), ("dirC", 0.5)], k=1)
    sel_ok = winners == ["dirB"]
    ok = inherited_claude and inherited_skill and memory_wiped and sel_ok
    print(f"  child inherited CLAUDE.md={inherited_claude} skill={inherited_skill}  session-memory wiped={memory_wiped}")
    print(f"  select_winners top-1 of (A=.2,B=.9,C=.5) → {winners}  (expect ['dirB'])")
    return ("evolve", ok, {"inherited": [inherited_claude, inherited_skill], "wiped": memory_wiped, "select": winners})


async def main():
    results = []
    for coro in (test_blackboard(), test_metacog(), test_season()):
        try:
            results.append(await coro)
        except Exception as e:
            import traceback; traceback.print_exc()
            results.append((getattr(coro, '__name__', 'world'), False, {"error": f"{type(e).__name__}: {e}"}))
    try:
        results.append(test_evolve())
    except Exception as e:
        import traceback; traceback.print_exc(); results.append(("evolve", False, {"error": str(e)}))

    print("\n" + "=" * 60 + "\nWORLD-FEATURE TALLY")
    for name, ok, info in results:
        print(f"  {'✓ PASS' if ok else '✗ FAIL'}  {name}")
    json.dump([[n, ok, i] for n, ok, i in results], open(os.path.join(SD, "worlds_results.json"), "w"), indent=2, default=str)

asyncio.run(main())
sys.stdout.flush()
os._exit(0)
