"""
darkfactory.py — the ladder of orders as typed sims, PURE ASSEMBLY of the atoms.

    Driver → World() → Formula1Stable() → Racetrack() → (Championship…)
     agent    market      R&D loop           RCT           replicated RCTs
   (opinion) (selection) (directed evol.)  (CAUSAL)       (meta-science)

The D∞ reading (lfpoop/dinfinity.py is the proof-object; the tower is D_{n+1}=[D_n→D_n]):

  * the CAR = the config that parameterizes a SkillcraftWorld — the self-simulated
    artifact (Poimandres). A car IS a world-parameterization; racing it IS running
    the world. Everything else is an effect of the car's fitness.
  * a Formula1Stable = a map cars→cars: the dev seat proposes a delta, the
    QUARANTINE GATE materializes the candidate car in a sandbox world and EXECUTES
    it (materialize → execute → test — the lfpoop loop as CI); a gate failure is
    DEATH — the lineage is extinct and the dev seat reruns with the cause as
    feedback. Built as loop_refine(proposer, gate) — the SDNA DUO/EvalChain atom.
  * a Racetrack = the causal gate OVER the stable: the survivor races the incumbent
    — two IDENTICAL deterministic drivers, same track, same rounds, ONE variable
    (the car). tournament([control, treatment], race_judge). SHIP iff treatment
    STRICTLY beats control; ties and losses REVERT. Correlation never ships a car.

The one law holds everywhere: the PROPOSER seat is the only generative slot — any
Link drops in (a scripted fn, a MiniMax runtime, a whole dev-WoS via
world_as_agent — the polymorphic slot IS the ep-pair embedding). The gate, the
track, the drivers, the judge, the fitness are CODE: execution and measurement.

Determinism note (honest): the shipped drivers are deterministic, so the RCT here
is ZERO-noise — one race per arm is a sound comparison. With stochastic (LLM)
drivers you would run replicates per arm; the topology is unchanged.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .chain_ontology import Link, LinkResult, LinkStatus
from .topologies import loop_refine, tournament
from .skillcraft import SkillcraftWorld, initial_state, craft_skill, record_test


# ── the car interface (the factory is GENERIC over the car — the D∞ point in
#    code: the orders never inspect what the car is, only race/gate/mutate it) ──
@dataclass
class CarKind:
    """The three verbs every order needs, injectable:
    race(car, workdir, tag) -> telemetry (async; must carry 'fitness');
    viability(car, workdir) -> {alive, cause, telemetry} (async — the gate);
    apply_delta(car, delta) -> candidate (sync)."""
    race: Callable
    viability: Callable
    apply_delta: Callable
    name: str = "carkind"


# ── the car (the self-simulated artifact — config as genome) ──────────────────
def new_car(ask_price: int = 80, starting_gold: int = 100) -> Dict[str, Any]:
    """A fresh car: the tunable parameterization of the market world."""
    return {"ask_price": ask_price, "starting_gold": starting_gold,
            "generation": 0, "lineage": []}


def apply_delta(car: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    """Candidate = car + delta (generation+1). Values are int-coerced when they
    parse; a nonsense value is APPLIED AS-IS — the gate kills bad cars, code does
    not silently correct them (the dark-factory ethic: selection, not sanitation)."""
    cand = {k: v for k, v in car.items() if k not in ("lineage",)}
    for k, v in (delta or {}).items():
        if k in ("generation", "lineage"):
            continue
        try:
            cand[k] = int(v)
        except (TypeError, ValueError):
            cand[k] = v
    cand["generation"] = car.get("generation", 0) + 1
    cand["lineage"] = []                       # lineage lives on the factory's car
    return cand


# ── the identical drivers (deterministic; parameterized ONLY by the car) ──────
class _Seller(Link):
    """Crafts one real skill (+ test record) on first move, then posts a listing
    at car['ask_price'] EVERY round. A rejected post (bad price) is logged by the
    arena and the driver survives — the car's flaw shows up as zero throughput."""

    def __init__(self, name: str, agents_root: str, car: Dict[str, Any]):
        self.name, self.root, self.car = name, agents_root, car
        self._tid: Optional[str] = None
        self._sp: Optional[str] = None

    async def execute(self, context=None, **_):
        c = dict(context or {})
        if self._tid is None:
            self._sp = craft_skill(self.root, self.name, "race_artifact",
                                   "# the car's product\nreal executable skill body")
            self._tid = record_test(self.root, self.name, self._sp, "pass")
        c["action"] = {"type": "trade_post", "skill_path": self._sp,
                       "price": self.car.get("ask_price"), "test_id": self._tid,
                       "rarity": "common", "description": "race artifact"}
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class _Buyer(Link):
    """Buys the cheapest affordable listing that isn't its own; else searches."""

    def __init__(self, name: str):
        self.name = name

    async def execute(self, context=None, **_):
        c = dict(context or {})
        board = c.get("board", {})
        me = board.get("agents", {}).get(self.name, {})
        gold = me.get("gold", 0)
        listings = sorted((l for l in board.get("trade_board", [])
                           if l["seller"] != self.name and l["price"] <= gold),
                          key=lambda l: l["price"])
        c["action"] = ({"type": "trade_buy", "listing_id": listings[0]["listing_id"]}
                       if listings else {"type": "search"})
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


# ── ORDER 0: World() — run the car, read the telemetry ────────────────────────
async def run_world(car: Dict[str, Any], workdir: str, rounds: int = 5,
                    tag: str = "run") -> Dict[str, Any]:
    """One deterministic race of the car: fresh dirs, two identical drivers,
    `rounds` rounds, one season. FITNESS = completed trades (market throughput).
    Telemetry additionally carries gold state + rejection count (the arena's
    kill-criteria log) + gold conservation (a real WoS invariant: with no quests,
    total gold is constant under atomic trades)."""
    root = tempfile.mkdtemp(prefix=f"{tag}-", dir=workdir)
    agents_root = os.path.join(root, "agents")
    quests_root = os.path.join(root, "quests")
    os.makedirs(quests_root, exist_ok=True)
    seller, buyer = "seller_1", "buyer_1"
    world = SkillcraftWorld(
        agents={seller: _Seller(seller, agents_root, car), buyer: _Buyer(buyer)},
        agents_root=agents_root, quests_root=quests_root,
        rounds=rounds, seasons=1, name=f"track:{tag}")
    board0 = initial_state([seller, buyer])
    for a in board0["agents"].values():
        a["gold"] = car.get("starting_gold", 100)
    res = await world.execute({"board": board0})
    b = res.context["board"]
    # KNOWN GAP: _blackboard_log does not surface through the Season wrapper
    # (the gauntlet living-note), so this count is OBSERVED rejections only —
    # 0 here means "unobserved", not "none happened".
    log = res.context.get("_blackboard_log", [])
    total0 = 2 * car.get("starting_gold", 100)
    total1 = sum(a["gold"] for a in b["agents"].values())
    return {"tag": tag, "fitness": len(b["trade_history"]),
            "trades": len(b["trade_history"]),
            "gold": {n: a["gold"] for n, a in b["agents"].items()},
            "rejections_observed": sum(1 for e in log if not e.get("ok")),
            "gold_conserved": total0 == total1, "car": dict(car)}


# ── ORDER 1's CI: the quarantine gate (materialize → execute → test) ──────────
async def quarantine_gate(candidate: Dict[str, Any], workdir: str,
                          rounds: int = 5) -> Dict[str, Any]:
    """Materialize the candidate car in a QUARANTINED sandbox world, execute a
    full race, test the invariants. Any failure = DEATH:
      1. the run completes (arena crash = dead);
      2. gold is conserved (a broken economy = dead);
      3. the market is ALIVE — ≥1 completed trade (a car whose config makes
         trading impossible — price 0, unaffordable ask — is economically dead)."""
    try:
        tel = await run_world(candidate, workdir, rounds=rounds, tag="quarantine")
    except Exception as e:                       # a car that crashes the arena
        return {"alive": False, "cause": f"crash: {type(e).__name__}: {e}",
                "telemetry": None}
    if not tel["gold_conserved"]:
        return {"alive": False, "cause": "gold not conserved (economy broken)",
                "telemetry": tel}
    if tel["trades"] < 1:
        rej = tel.get("rejections_observed", 0)
        return {"alive": False,
                "cause": ("market dead: 0 trades"
                          + (f" ({rej} rejected moves observed)" if rej else "")),
                "telemetry": tel}
    return {"alive": True, "cause": "pass", "telemetry": tel}


def config_kind(rounds: int = 5) -> CarKind:
    """The original car: a config dict raced as a SkillcraftWorld market."""
    async def _race(car, workdir, tag="run"):
        return await run_world(car, workdir, rounds=rounds, tag=tag)

    async def _viability(car, workdir):
        return await quarantine_gate(car, workdir, rounds=rounds)

    return CarKind(race=_race, viability=_viability, apply_delta=apply_delta,
                   name="config-car")


class _GateLink(Link):
    """The critic seat of the dev DUO. Reads the proposed delta from
    ctx['delta'] (or ctx['action'] — so a world_as_agent proposer plugs in
    unchanged), builds the candidate, runs the quarantine. Death → the lineage
    is recorded extinct and the CAUSE becomes ctx['gate_feedback'] for the
    proposer's next attempt (the EvalChain loop is the dev-deity's rerun)."""
    name = "quarantine_gate"

    def __init__(self, workdir: str, kind: CarKind):
        self.workdir, self.kind = workdir, kind

    async def execute(self, context=None, **_):
        c = dict(context or {})
        delta = c.get("delta") or c.get("action") or {}
        candidate = self.kind.apply_delta(c["car"], delta)
        verdict = await self.kind.viability(candidate, self.workdir)
        c["gate_passed"] = verdict["alive"]
        if verdict["alive"]:
            c["candidate"], c["candidate_delta"] = candidate, delta
        else:
            c.setdefault("extinct", []).append(
                {"delta": delta, "cause": verdict["cause"],
                 "generation": candidate["generation"]})
            c["gate_feedback"] = verdict["cause"]
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


def proposer_from_fn(fn: Callable[[Dict[str, Any]], Dict[str, Any]],
                     name: str = "dev_seat") -> Link:
    """Adapt a plain callable ctx→delta into the dev seat. The polymorphic slot:
    any Link works here — this helper, a MiniMax runtime wrapper, or a WHOLE
    dev-world via world_as_agent(dev_world, derive_delta)."""
    class _P(Link):
        async def execute(self, context=None, **_):
            c = dict(context or {})
            c["delta"] = fn(c)
            return LinkResult(status=LinkStatus.SUCCESS, context=c)
    p = _P()
    p.name = name
    return p


# ── ORDER 1: Formula1Stable() — the R&D loop (dev ⊕ gate = the DUO atom) ──────
class Formula1Stable(Link):
    """cars→cars: develop a gate-surviving candidate from the incumbent.
    loop_refine(proposer, quarantine_gate) — SDNA's EvalChain: propose → gate →
    (death → feedback → repropose) until survival or max_attempts. Returns the
    survivor in ctx['candidate'] (None ⇒ every lineage died)."""

    def __init__(self, proposer: Link, workdir: str, rounds: int = 5,
                 max_attempts: int = 3, kind: Optional[CarKind] = None,
                 name: str = "formula1_stable"):
        self.name = name
        kind = kind or config_kind(rounds)
        self.loop = loop_refine(proposer, _GateLink(workdir, kind),
                                max_cycles=max_attempts,
                                approval_key="gate_passed", name=f"{name}:duo")

    async def execute(self, context=None, **_):
        return await self.loop.execute(dict(context or {}))


# ── ORDER 2: Racetrack() — the RCT (tournament of two identical drivers) ──────
class _TrackArm(Link):
    """One arm of the split: race the given car on a fresh track; the result
    rides ctx['output'] so tournament's gather labels it output:<arm>."""

    def __init__(self, arm: str, car: Dict[str, Any], workdir: str,
                 kind: CarKind):
        self.name, self.car, self.workdir, self.kind = arm, car, workdir, kind

    async def execute(self, context=None, **_):
        c = dict(context or {})
        tel = await self.kind.race(self.car, self.workdir, tag=self.name)
        out = json.dumps({"arm": self.name, "fitness": tel["fitness"],
                          **{k: tel[k] for k in ("trades", "gold",
                                                 "rejections_observed",
                                                 "failing_inputs", "cases")
                             if k in tel}})
        c["output"] = out
        c[f"output:{self.name}"] = out      # the worker namespaces its own output
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


class _RaceJudge(Link):
    """The race judge (code, not opinion): SHIP iff treatment STRICTLY beats
    control on fitness. A tie is a REVERT — change has cost; correlation and
    coin-flips never ship a car."""
    name = "race_judge"

    async def execute(self, context=None, **_):
        c = dict(context or {})
        arms = {}
        for arm in ("control", "treatment"):
            arms[arm] = json.loads(c.get(f"output:{arm}", "{}") or "{}")
        f_c = arms["control"].get("fitness", 0)
        f_t = arms["treatment"].get("fitness", 0)
        c["race"] = {"control": arms["control"], "treatment": arms["treatment"]}
        c["verdict"] = "SHIP" if f_t > f_c else "REVERT"
        return LinkResult(status=LinkStatus.SUCCESS, context=c)


def racetrack(control_car: Dict[str, Any], candidate_car: Dict[str, Any],
              workdir: str, rounds: int = 5,
              kind: Optional[CarKind] = None) -> Link:
    """The always-on split: tournament([control, treatment], race_judge)."""
    kind = kind or config_kind(rounds)
    return tournament(
        [_TrackArm("control", control_car, workdir, kind),
         _TrackArm("treatment", candidate_car, workdir, kind)],
        _RaceJudge(), name="racetrack")


# ── the composed factory (the full ladder, one cycle at a time) ───────────────
class DarkFactory:
    """Racetrack(Formula1Stable(World)) — holds the incumbent car; each cycle():
    ORDER 0 read the incumbent's telemetry → ORDER 1 the stable develops a
    gate-surviving candidate (deaths recorded) → ORDER 2 the racetrack renders
    the causal verdict → SHIP mutates the car (generation+1) and the lineage
    records everything either way. The proposer seat is the only generative
    slot; every gate below it is code."""

    def __init__(self, car: Optional[Dict[str, Any]] = None,
                 workdir: Optional[str] = None, rounds: int = 5,
                 max_attempts: int = 3, kind: Optional[CarKind] = None):
        self.car = car or new_car()
        self.workdir = workdir or tempfile.mkdtemp(prefix="darkfactory-")
        self.rounds, self.max_attempts = rounds, max_attempts
        self.kind = kind or config_kind(rounds)

    async def cycle(self, proposer: Link) -> Dict[str, Any]:
        # ORDER 0 — the incumbent runs; its telemetry is the dev seat's input.
        telemetry = await self.kind.race(self.car, self.workdir,
                                         tag="incumbent")
        # ORDER 1 — the stable develops (propose → quarantine → death/rerun).
        stable = Formula1Stable(proposer, self.workdir, rounds=self.rounds,
                                max_attempts=self.max_attempts, kind=self.kind)
        r = await stable.execute({"car": dict(self.car), "telemetry": telemetry})
        ctx = r.context or {}
        extinct: List[Dict[str, Any]] = ctx.get("extinct", [])
        candidate = ctx.get("candidate")
        if not ctx.get("gate_passed") or candidate is None:
            report = {"telemetry": telemetry, "extinct": extinct,
                      "candidate": None, "verdict": "ALL_LINEAGES_EXTINCT",
                      "car": dict(self.car)}
            self.car["lineage"].append({"verdict": report["verdict"],
                                        "extinct": extinct})
            return report
        # ORDER 2 — the RCT. The factory ALWAYS deploys splits.
        race = await racetrack(self.car, candidate, self.workdir,
                               rounds=self.rounds, kind=self.kind).execute({})
        rc = race.context or {}
        verdict, arms = rc["verdict"], rc["race"]
        entry = {"delta": ctx.get("candidate_delta"), "verdict": verdict,
                 "fitness_control": arms["control"].get("fitness"),
                 "fitness_treatment": arms["treatment"].get("fitness"),
                 "extinct": extinct}
        if verdict == "SHIP":
            lineage = self.car["lineage"] + [entry]
            self.car = dict(candidate)
            self.car["lineage"] = lineage
        else:
            self.car["lineage"].append(entry)
        return {"telemetry": telemetry, "extinct": extinct,
                "candidate": candidate, "verdict": verdict, "race": arms,
                "car": dict(self.car)}


__all__ = ["CarKind", "config_kind", "new_car", "apply_delta", "run_world",
           "quarantine_gate", "proposer_from_fn", "Formula1Stable", "racetrack",
           "DarkFactory"]
