"""
skillcraft.py — the REAL World of Skillcraft, re-assembled from the cave-teams atoms.

WoS's control mechanics are already atoms here (blackboard = the shared world state, season =
carry/reset/ratchet, the deity = the adjudicator). Its ECONOMY was never an atom — it lived as
`execute.sh` (a single guarded action-mutator on game.json) + `deity-season.sh` (the season advance,
bug-bounty, typed rarity ratchet). This module ports that economy FAITHFULLY as the GameWorld's
mutator so the whole game runs on the engine:

    SkillcraftWorld = season( blackboard(agents ↔ game_state ↔ deity, mutator=skillcraft_mutator),
                              advance = skillcraft_advance )

The economy state (agents/gold/counters, trade_board, trade_history, lfg_board, quest_log,
deity_bulletin, season) lives on the blackboard. The EMBODIMENT is real files: an agent crafts a real
`crafted/<name>.md` and a `test.sh`-style pass mints `crafted/.tests/<id>.json` — the mutator's
trade_post guard checks BOTH (skill file exists + a matching test record) exactly like execute.sh.
Guard failures raise ValueError → the blackboard logs the rejection and the arena survives (the
`exit 1` of the bash version). Every guard here is a fossilized bug fix from 10 real seasons — ported
verbatim in intent, not re-invented.

Source of truth (ported line-for-line): world-of-skillcraft/agents/_template/.../execute.sh (7 verbs)
+ world-of-skillcraft/deity-season.sh (advance/bounty/bulletin/ratchet).
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .blackboard import blackboard
from .season import season
from .gameworld import GameWorld

RARITIES = ["common", "uncommon", "rare", "epic", "legendary"]  # legendary = deity-only


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nonce(state: Dict[str, Any]) -> int:
    state["_nonce"] = int(state.get("_nonce", 0)) + 1
    return state["_nonce"]


# ── the world state (game.json shape) ────────────────────────────────────────
def initial_state(agent_ids: List[str], season_number: int = 1,
                  rarity_consensus: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """A fresh WoS game state — the blackboard's board."""
    return {
        "season": {"number": season_number, "title": None, "started_at": None,
                   # the typed quality ratchet (the standard only tightens across seasons)
                   "rarity_consensus": dict(rarity_consensus or {
                       "template": "common", "lens": "uncommon", "prosthesis": "rare",
                       "towering": "rare", "combiner": "uncommon", "persona": "rare",
                       "recipe": "epic"})},
        "agents": {a: {"gold": 100, "last_action": None, "last_action_at": None,
                       "skills_crafted": 0, "trades_completed": 0, "quests_completed": 0}
                   for a in agent_ids},
        "trade_board": [], "trade_history": [], "lfg_board": [], "quest_log": {},
        "deity_bulletin": [], "bug_reports": [],
    }


# ── the embodiment helpers (real files — the artifact IS the product) ─────────
def craft_skill(agents_root, agent: str, name: str, content: str,
                skill_type: str = "template") -> str:
    """Agent writes a real executable skill file: <agent>/crafted/<name>.md. Returns its relative
    skill_path (as execute.sh stores it: 'crafted/<name>.md'). Non-rivalrous — the crafter keeps it."""
    d = Path(agents_root) / agent / "crafted"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(content, encoding="utf-8")
    return f"crafted/{name}.md"


def record_test(agents_root, agent: str, skill_path: str, result: str = "pass",
                test_id: Optional[str] = None) -> str:
    """Mint a test record (what test.sh writes after running the skill through a fresh model):
    <agent>/crafted/.tests/<test_id>.json = {test_id, skill_path, result}. trade_post REQUIRES it."""
    tdir = Path(agents_root) / agent / "crafted" / ".tests"
    tdir.mkdir(parents=True, exist_ok=True)
    tid = test_id or f"test_{abs(hash((agent, skill_path, result))) % (16**12):012x}"
    (tdir / f"{tid}.json").write_text(
        json.dumps({"test_id": tid, "skill_path": skill_path, "result": result}), encoding="utf-8")
    return tid


# ── the economy mutator (execute.sh, ported verb-for-verb) ────────────────────
def skillcraft_mutator(agents_root, quests_root) -> Callable:
    """Return the blackboard mutator (state, agent, action) -> state. `action` is the WoS action dict
    (`{"type": ..., ...}` — the `.action` object execute.sh reads). Guard failures raise ValueError,
    which the blackboard logs as a rejected move (the bash `exit 1`). agents_root holds the per-agent
    dirs (crafted/, crafted/.tests/); quests_root holds canonical quest defs (anti-injection reward)."""
    agents_root = Path(agents_root)
    quests_root = Path(quests_root)

    def mut(state: Dict[str, Any], agent: str, action: Any) -> Dict[str, Any]:
        if not isinstance(action, dict):
            raise ValueError(f"non-dict action: {action!r}")
        s = json.loads(json.dumps(state))          # copy-on-write (atomic apply, like jq→tmp→mv)
        t = action.get("type", "unknown")
        ag = s["agents"].setdefault(agent, {"gold": 100, "skills_crafted": 0,
                                            "trades_completed": 0, "quests_completed": 0})
        now = _ts()

        def stamp(who=agent):
            s["agents"][who]["last_action"] = t
            s["agents"][who]["last_action_at"] = now

        if t == "trade_post":
            skill_path = str(action.get("skill_path", ""))
            price = action.get("price")
            test_id = action.get("test_id") or ""
            rarity = action.get("rarity", "common")
            desc = action.get("description", "No description")
            if not test_id:                                            # mandatory testing (S7)
                raise ValueError("test_id is required. Run test_skill first.")
            if not isinstance(price, int) or price <= 0:               # positive price
                raise ValueError(f"Price must be positive (got {price})")
            if not (agents_root / agent / skill_path).is_file():       # skill file exists
                raise ValueError(f"Skill file not found at {skill_path}")
            trec = agents_root / agent / "crafted" / ".tests" / f"{test_id}.json"
            if not trec.is_file():                                     # test record exists
                raise ValueError(f"Test record not found for {test_id}")
            tested = json.loads(trec.read_text()).get("skill_path", "")
            if tested != skill_path:                                   # …and matches this skill
                raise ValueError(f"Test record {test_id} is for '{tested}', not '{skill_path}'")
            lid = f"listing_{_nonce(s)}_{agent}"
            s["trade_board"].append({"listing_id": lid, "seller": agent, "skill_path": skill_path,
                                     "price": price, "rarity": rarity, "description": desc,
                                     "posted_at": now, "test_id": test_id})
            stamp()

        elif t == "trade_buy":
            lid = str(action.get("listing_id", ""))
            listing = next((l for l in s["trade_board"] if l["listing_id"] == lid), None)
            if listing is None:
                raise ValueError(f"Listing {lid} not found")
            seller, price = listing["seller"], listing["price"]
            if agent == seller:                                        # no self-buy
                raise ValueError("Cannot buy your own listing")
            if ag["gold"] < price:                                     # gold sufficiency
                raise ValueError(f"Not enough gold. Have {ag['gold']}, need {price}")
            s["agents"][agent]["gold"] -= price                        # atomic transfer
            s["agents"][seller]["gold"] += price
            s["agents"][agent]["trades_completed"] += 1
            s["agents"][seller]["trades_completed"] += 1
            s["trade_board"] = [l for l in s["trade_board"] if l["listing_id"] != lid]
            s["trade_history"].append({"listing_id": lid, "seller": seller, "buyer": agent,
                                       "skill_path": listing["skill_path"], "price": price,
                                       "rarity": listing.get("rarity", "unrated"), "at": now})
            stamp()

        elif t == "quest_accept":
            qid = str(action.get("quest_id", ""))
            log = s["quest_log"].setdefault(agent, [])
            if any(q["quest_id"] == qid and q.get("status") in ("active", "completed") for q in log):
                raise ValueError(f"Quest {qid} already accepted or completed")
            log.append({"quest_id": qid, "accepted_at": now, "status": "active"})
            stamp()

        elif t == "quest_complete":
            qid = str(action.get("quest_id", ""))
            skill_path = str(action.get("skill_path", ""))
            qfile = quests_root / f"{qid}.md"                          # reward from CANONICAL file…
            if not qfile.is_file():
                raise ValueError(f"Quest definition not found for {qid}")
            reward = _grep_reward(qfile.read_text())                   # …NOT agent input (anti-injection)
            log = s["quest_log"].get(agent, [])
            if not any(q["quest_id"] == qid and q.get("status") == "active" for q in log):
                raise ValueError(f"Quest {qid} is not active in your quest log. Accept it first.")
            ag["gold"] += reward
            ag["skills_crafted"] += 1
            ag["quests_completed"] += 1
            for q in log:
                if q["quest_id"] == qid:
                    q.update(status="completed", completed_at=now, skill_path=skill_path)
            stamp()

        elif t == "lfg_post":
            pid = f"lfg_{_nonce(s)}_{agent}"
            s["lfg_board"].append({"party_id": pid, "leader": agent,
                                   "specializations": action.get("specializations", ""),
                                   "looking_for": action.get("looking_for", ""),
                                   "posted_at": now, "members": [agent]})
            stamp()

        elif t == "lfg_join":
            pid = str(action.get("party_id", ""))
            party = next((p for p in s["lfg_board"] if p["party_id"] == pid), None)
            if party is None:
                raise ValueError(f"Party {pid} not found on LFG board")
            if agent in party["members"]:
                raise ValueError(f"Already a member of party {pid}")
            party["members"].append(agent)
            stamp()

        elif t == "challenge":
            lid = str(action.get("listing_id", ""))
            listing = next((l for l in s["trade_board"] if l["listing_id"] == lid), None)
            if listing is not None and listing["seller"] == agent:     # no self-challenge
                raise ValueError("Cannot challenge your own listing")
            ch = (listing or {}).get("challenges", []) if listing else []
            if any(c["challenger"] == agent for c in ch):
                raise ValueError(f"Already challenged listing {lid}")
            if listing is not None:
                listing.setdefault("challenges", []).append(
                    {"challenger": agent, "assessment": action.get("assessment", ""),
                     "reason": action.get("reason", ""), "at": now})
            stamp()

        elif t == "bug_report":
            # audit the GAME ITSELF (this economy) for an exploit — the bounty loop's supply side.
            # (WoS files these via a separate report.sh; here it's a first-class move onto the board.)
            bid = f"bug_{_nonce(s)}_{agent}"
            s.setdefault("bug_reports", []).append(
                {"id": bid, "reporter": agent, "title": str(action.get("title", ""))[:120],
                 "description": str(action.get("description", ""))[:500],
                 "reproduction": str(action.get("reproduction", ""))[:500],
                 "severity": action.get("severity", "low"), "status": "open", "reward_paid": False})
            stamp()

        else:                                                          # move/learn/search/remember…
            stamp()
        return s

    return mut


def _grep_reward(text: str) -> int:
    """Reward from a quest .md — '## Reward' then first number, else 'N gold', else 50 (execute.sh)."""
    m = re.search(r"##\s*Reward\s*\n+.*?(\d+)", text, re.I | re.S)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*gold", text, re.I)
    return int(m.group(1)) if m else 50


# ── the season advance (deity-season.sh advance, ported) ──────────────────────
def skillcraft_advance(bug_reports: Optional[List[Dict[str, Any]]] = None) -> Callable:
    """Return advance(board, season_num) -> board: pay valid-unpaid bug bounties (100g/bug, grouped by
    reporter, mark paid) BEFORE the reset, then archive→previous_season, reset gold=100 + counters,
    wipe the boards, CARRY the rarity_consensus (the ratchet) + the deity_bulletin + the bug ledger,
    then add bounty gold on top. The bug ledger is `board["bug_reports"]` (deity-validated on the
    board); pass `bug_reports` only to use a side-channel ledger instead."""

    def advance(board: Dict[str, Any], n: int) -> Dict[str, Any]:
        b = json.loads(json.dumps(board))
        cur = b["season"]
        bugs = bug_reports if bug_reports is not None else b.get("bug_reports", [])
        # 1. tally valid+unpaid bounties by reporter, mark paid
        payouts: Dict[str, int] = {}
        for bug in bugs:
            if bug.get("status") == "valid" and not bug.get("reward_paid", False):
                payouts[bug["reporter"]] = payouts.get(bug["reporter"], 0) + 100
                bug["reward_paid"] = True
        # 2. archive + ratchet + reset + wipe (rarity_consensus + deity_bulletin CARRY)
        b["season"] = {"number": cur["number"] + 1, "title": None, "started_at": None,
                       "previous_season": {"number": cur["number"], "title": cur.get("title") or "Untitled",
                                           "rarity_consensus": cur["rarity_consensus"],
                                           "top_performer": cur.get("top_performer"),
                                           "notable_events": cur.get("notable_events", [])},
                       "rarity_consensus": cur["rarity_consensus"]}
        for a in b["agents"].values():
            a.update(gold=100, last_action=None, last_action_at=None,
                     skills_crafted=0, trades_completed=0, quests_completed=0)
        b["trade_board"], b["trade_history"], b["lfg_board"], b["quest_log"] = [], [], [], {}
        # deity_bulletin persists (standing rulebook); bug ledger persists (separate)
        # 3. bounty gold on TOP of the 100 floor
        for reporter, amt in payouts.items():
            if reporter in b["agents"]:
                b["agents"][reporter]["gold"] += amt
        b["_bounties_paid"] = payouts
        return b

    return advance


# ── the deity (bug validation + bulletins — season-boundary + human-gated) ────
def validate_bug(bug_reports: List[Dict[str, Any]], bug_id: str, status: str = "valid") -> None:
    if status not in ("valid", "invalid"):
        raise ValueError("Status must be 'valid' or 'invalid'")
    for bug in bug_reports:
        if bug.get("id") == bug_id:
            bug["status"] = status


def post_bulletin(state: Dict[str, Any], message: str) -> None:
    state.setdefault("deity_bulletin", []).append(
        {"season": state["season"]["number"], "message": message, "posted_at": _ts()})


# ── the composed World ────────────────────────────────────────────────────────
class SkillcraftWorld(GameWorld):
    """The real WoS as a GameWorld: blackboard(agents ↔ game_state ↔ deity, skillcraft_mutator) wrapped
    in a season whose advance pays bounties + ratchets the typed rarity standard. Instantiate with the
    player agent Links, the agent-dirs root (crafted/ + .tests/), the canonical quests root, and the
    (deity-validated) bug ledger."""

    def __init__(self, agents: Dict[str, Any], agents_root, quests_root,
                 deity: Optional[Any] = None, bug_reports: Optional[List[Dict[str, Any]]] = None,
                 rounds: int = 1, seasons: int = 1, name: str = "skillcraft"):
        super().__init__(agents, skillcraft_mutator(agents_root, quests_root), deity=deity,
                         advance=skillcraft_advance(bug_reports),
                         rounds=rounds, seasons=seasons, state_key="board", name=name)


__all__ = ["SkillcraftWorld", "skillcraft_mutator", "skillcraft_advance", "initial_state",
           "craft_skill", "record_test", "validate_bug", "post_bulletin", "RARITIES"]
