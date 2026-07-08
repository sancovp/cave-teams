"""
cave.py — the metacontrol function (the super-compiled top).

THIS IS NOT HOW YOU PROGRAM WITH cave-teams. You program with the native API — the rolled-up
functions (`seq`, `par`, `gate`, `tournament`, `AgentLink`, `add_condition`, …) and the `>>` / `|`
DSL. That is ergonomic and direct, and it is what the skills teach.

`cave()` is the layer ABOVE: ONE metacontrol function — a construct/execute chain interpreter whose
tree is made of OP-SLOTS. An "op" is just a NAME registered to a builder that returns a Link (a step);
`{"op":"seq",...}` = "look up the builder `seq`, hand it this node, get a Link." The canonical ops
below are simply builders that ship PRE-REGISTERED — they are NOT a closed menu. A slot can hold:
  • a canonical op (seq/par/gate/agent/tournament/…),
  • ANY imported function you map IO to/from — `{"op":"call","import":"pkg.mod.fn"}` or a register_fn'd
    callable `{"op":"call","fn":"name"}`,
  • a saved config BY NAME — `{"op":"golden","name":"crew"}` loads a proven team as a step,
  • a whole LEADER-DRIVEN team — `{"op":"team_run", ...}` (the message-state-machine runtime).
You EXTEND the op set with `register(op, builder)` / `register_fn(name, callable)`; goldenizing a team
makes it a callable op too.

TWO runtimes reachable through the door: `execute` runs the composition IN-PROCESS (a function, threading
a dict — the default); the `team_run` op runs the LEADER-DRIVEN plane (a leader routes messages between
agents over files/inboxes with guardrail conditions — the `run_team`/`cave_team` runtime).

Sync, no daemon, no agent-that-builds-for-you: you (or your agent) write the spec; `cave()` runs it.
The difference from using the lib directly: in Python you interleave arbitrary custom code between steps;
in a `cave()` data-spec the code must already EXIST and be referenced (imported by path, or register_fn'd
by name) — you don't inline it, you point at it.

Spec node:  {"op": "<name>", ...args, nested specs under child keys}
    {"op":"seq","links":[<spec>,...]}                      run in order
    {"op":"par","links":[<spec>,...]}                      run at once
    {"op":"gate","body":<spec>,"evaluator":<spec>}         loop until approved
    {"op":"tournament","competitors":[<spec>,...],"judge":<spec>}
    {"op":"agent","name":"x","system_prompt":"...","backend":"minimax"}   # a leaf
    {"op":"agent","name":"x","persona":"<name|spec>"}      # persona MADE by SI/meta-APE → this leaf
    {"op":"call","import":"pkg.mod.fn","input_key":"k","output_key":"o"}  # ANY function as a step
    {"op":"golden","name":"crew"}                          # load a saved config BY NAME
    {"op":"team_run","topology":<spec>,"leader":"<fn>","runtimes":{...},"task":"..."}  # leader-driven

Uniform envelope (cave() never throws):
    {"status":"construction_error","error":...,"hint":"read the cave-<op> skill"}
    {"status":"described","description":...,"spec":...}
    {"status":"runtime_error","error":...}
    {"status":"success"|"error"|..., "context":..., "error":...}     # from the run
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .chain_ontology import Link, LinkResult, LinkStatus
from .algebra import seq, par, gate, choice, skip, team, dovetail
from .topologies import tournament, loop_refine, round_robin, synthesis_gate
from .wiring import AgentRef
from .dag import dag
from .dovetail import DovetailModel
from .blackboard import blackboard
from .season import season
from .gameworld import GameWorld

# ── the registry: op-name → builder(spec) → Link.  THE extension seam. ────────
_REGISTRY: Dict[str, Callable[[dict], Link]] = {}


def register(op: str, builder: Callable[[dict], Link]) -> None:
    """Add a canonical op to the metacontrol surface (extend what cave() can drive).
    This is how a goldenized team / a new native op becomes callable through cave()."""
    _REGISTRY[op] = builder


def registered_ops() -> List[str]:
    return sorted(_REGISTRY)


# ── the callable registry: named Python callables for callable-heavy ops ──────
_FN_REGISTRY: Dict[str, Callable] = {}


def register_fn(name: str, fn: Callable) -> None:
    """Register a named callable (mutator / deity-action / advance / guard) so callable-heavy ops
    (blackboard, world, season) can be driven from a pure-data spec by referencing it BY NAME."""
    _FN_REGISTRY[name] = fn


def registered_fns() -> List[str]:
    return sorted(_FN_REGISTRY)


def _fn(ref, what: str, required: bool = False):
    """Resolve a callable: pass-through if already callable, else look it up by name.
    required=True turns a missing callable into a construction error (caught by cave())."""
    if ref is None:
        if required:
            raise KeyError(f"'{what}' is required — register_fn() a callable and reference it by name")
        return None
    if callable(ref):
        return ref
    if ref in _FN_REGISTRY:
        return _FN_REGISTRY[ref]
    raise KeyError(f"unknown {what} '{ref}' — register it with register_fn(); known: {registered_fns()}")


def _dovetail_model(d: dict) -> DovetailModel:
    return DovetailModel(name=d.get("name", ""), expected_outputs=d.get("expected_outputs", []),
                         file_inputs=d.get("file_inputs", {}))


# ── the persona SEAM: cave-teams composes AGENTS; SI/meta-APE MAKES them. The agent leaf's `persona`
#    is resolved to a system_prompt through this pluggable compiler — a THIN handoff, NOT a dependency.
#    SI : ChainCompiler :: cave() : cave-teams — two peer doors that meet here, at the agent boundary. ─
_PERSONA_COMPILER: Optional[Callable[[Any], str]] = None


def set_persona_compiler(fn: Optional[Callable[[Any], str]]) -> None:
    """Register the persona compiler (the SI/meta-APE side): fn(persona_ref) -> system_prompt string.
    Keeps cave-teams decoupled from ChainCompiler — cave() just calls whatever you register."""
    global _PERSONA_COMPILER
    _PERSONA_COMPILER = fn


def _default_persona_compiler(ref: Any) -> str:
    """Default (import-if-present, like chain_ontology's uco/sdna fallback): the meta-APE persona door.
    dict ref → make_persona(spec); str ref → a saved persona template by name."""
    from prompt_engineering import make_persona, render_template  # optional; only if installed
    return make_persona(ref) if isinstance(ref, dict) else render_template(str(ref))


def _compile_persona(ref: Any) -> str:
    fn = _PERSONA_COMPILER
    if fn is None:
        try:
            fn = _default_persona_compiler
            out = fn(ref)
        except Exception as e:
            raise ValueError(
                f"agent 'persona' needs a compiler: set_persona_compiler(fn), or install "
                f"agent-prompt-engineering (the SI/meta-APE persona door). Underlying: {e}")
    else:
        out = fn(ref)
    return out if isinstance(out, str) else str(out)


def _build(spec: Any) -> Link:
    """Recursively build a native Link from a data spec by dispatching on spec['op']."""
    if isinstance(spec, Link):
        return spec
    if not isinstance(spec, dict) or "op" not in spec:
        raise ValueError("spec must be a dict with an 'op' key (or a Link)")
    op = spec["op"]
    if op not in _REGISTRY:
        raise KeyError(f"unknown op '{op}' — known ops: {registered_ops()}")
    return _REGISTRY[op](spec)


def _kids(spec: dict, key: str) -> List[Link]:
    return [_build(s) for s in spec.get(key, [])]


def _guard(route: dict) -> Callable[[Dict[str, Any]], bool]:
    """A serializable context-predicate for `choice` routes (guards are data, not lambdas)."""
    if "if_key" in route:
        k, v = route["if_key"], route.get("equals", True)
        return lambda ctx: ctx.get(k) == v
    if "if_contains" in route:
        k, sub = route["if_contains"]["key"], route["if_contains"]["text"]
        return lambda ctx: sub in str(ctx.get(k, ""))
    return lambda ctx: True


# ── roll the native API up into the registry (the instruction set) ────────────
register("skip", lambda s: skip())


def _agent_op(s: dict) -> Link:
    """An "agent" leaf. With system_prompt/persona/backend/model it is RUNNABLE (an AgentLink over an
    example-instance runtime — cave() executes it directly). `persona` is an SI/meta-APE persona ref
    (a name or a spec) compiled to the system_prompt via set_persona_compiler — the SI→cave handoff.
    A bare {"op":"agent","name":...} is a REFERENCE to a cave agent by name (AgentRef — compiled to
    team edges, run by run_team/team_run)."""
    if any(k in s for k in ("system_prompt", "backend", "model", "persona")):
        from .links import AgentLink
        system_prompt = _compile_persona(s["persona"]) if s.get("persona") is not None \
            else s.get("system_prompt", "")
        return AgentLink(s.get("name", "agent"), system_prompt=system_prompt,
                         backend=s.get("backend", "minimax"), model=s.get("model"))
    return AgentRef(s.get("name", "agent"))


register("agent", _agent_op)
register("seq", lambda s: seq(*_kids(s, "links"), name=s.get("name", "seq")))
register("par", lambda s: par(*_kids(s, "links"), name=s.get("name", "par")))
register("gate", lambda s: gate(
    _build(s["body"]), _build(s["evaluator"]),
    max_cycles=s.get("max_cycles", 3), approval_key=s.get("approval_key", "approved"),
    name=s.get("name", "gate")))
register("loop", lambda s: loop_refine(
    _build(s["worker"]), _build(s["critic"]),
    max_cycles=s.get("max_cycles", 3), name=s.get("name", "loop")))
register("tournament", lambda s: tournament(
    _kids(s, "competitors"), _build(s["judge"]), name=s.get("name", "tournament")))
register("map_reduce", lambda s: synthesis_gate(
    _kids(s, "workers"), _build(s["reducer"]), name=s.get("name", "map_reduce")))
register("round_robin", lambda s: round_robin(
    _kids(s, "links"), rounds=s.get("rounds", 1), name=s.get("name", "round_robin")))
register("choice", lambda s: choice(
    [(_guard(r), _build(r["link"])) for r in s.get("routes", [])],
    default=_build(s["default"]) if s.get("default") else None, name=s.get("name", "choice")))
register("team", lambda s: team(_build(s["inner"]), name=s.get("name", "team")))
register("dag", lambda s: dag(
    {k: _build(v) for k, v in s.get("nodes", {}).items()},
    deps=s.get("deps"), name=s.get("name", "dag")))
register("dovetail", lambda s: dovetail(
    _build(s["a"]), _dovetail_model(s.get("model", {})), _build(s["b"]),
    name=s.get("name", "dovetail")))
# callable-heavy ops: mutator/advance/deity referenced BY NAME (register_fn) → still pure-data spec
register("blackboard", lambda s: blackboard(
    {k: _build(v) for k, v in s.get("agents", {}).items()},
    _fn(s.get("mutator"), "mutator", required=True),
    adjudicator=_build(s["adjudicator"]) if s.get("adjudicator") else None,
    rounds=s.get("rounds", 1), state_key=s.get("state_key", "board")))
register("season", lambda s: season(
    _build(s["arena"]), advance=_fn(s.get("advance"), "advance"),
    seasons=s.get("seasons", 1), state_key=s.get("state_key", "board"), name=s.get("name", "season")))
register("world", lambda s: GameWorld.from_spec(
    s.get("spec", {}), {k: _build(v) for k, v in s.get("agents", {}).items()},
    _fn(s.get("mutator"), "mutator", required=True),
    deity=_build(s["deity"]) if s.get("deity") else None))

# ── the GENERIC op: ANY imported function as a chain step (map IO however you want) ───────────
def _call_op(s: dict) -> Link:
    """A step = ANY function. Import it by path (`"import":"pkg.mod.fn"`) or reference a register_fn'd
    callable (`"fn":"name"`); wrap it as a Link with IO mapping (`input_key` selects the input from the
    context, `output_key` stores the result). THIS is 'put any imported function in an op slot and map
    its IO' — the code must already exist; the spec points at it, it is not inlined."""
    from .sdna_bridge import as_link
    ref_name = None
    if s.get("import"):
        import importlib
        mod, _, fname = s["import"].rpartition(".")
        if not mod:
            raise ValueError(f"call: 'import' must be 'module.function', got {s['import']!r}")
        fn = getattr(importlib.import_module(mod), fname)
        ref_name = fname
    elif s.get("fn"):
        fn = _fn(s.get("fn"), "fn", required=True)
        ref_name = s["fn"] if isinstance(s["fn"], str) else None
    else:
        raise ValueError("call: give 'import':'pkg.mod.fn' or 'fn':'<register_fn name>'")
    name = s.get("name") or ref_name or getattr(fn, "__name__", "call")
    return as_link(fn, name=name, input_key=s.get("input_key"), output_key=s.get("output_key", "output"))


register("call", _call_op)


# ── the OTHER runtime as an op: run a LEADER-DRIVEN team through the door ──────────────────────
class _TeamRunLink(Link):
    """Runs the LEADER-DRIVEN team plane (run_team: a leader routes messages between agents over
    files/inboxes with guardrail conditions) as a Link, so `cave()` can reach BOTH runtimes. The
    topology (AgentRefs) compiles to edges; the leader + teammate RUNTIMES are objects, so reference
    them by name (register_fn'd). Returns the run envelope under ctx['team_result']."""

    def __init__(self, topology, task, team_dir, leader_ref, runtime_refs,
                 leader_mode="llm", max_steps=40, name="team_run"):
        self.topology = topology
        self.task = task
        self.team_dir = team_dir
        self.leader_ref = leader_ref
        self.runtime_refs = runtime_refs
        self.leader_mode = leader_mode
        self.max_steps = max_steps
        self.name = name

    async def execute(self, context=None, **kwargs):
        from .runner import run_team_async, llm_leader, file_leader
        leader_rt = _fn(self.leader_ref, "leader", required=True)
        # leader_mode: 'raw' = leader_rt IS a LeaderFn(ctx)->Proposal; 'llm'/'file' = wrap a runtime
        leader_fn = (leader_rt if self.leader_mode == "raw"
                     else file_leader(leader_rt) if self.leader_mode == "file"
                     else llm_leader(leader_rt))
        runtimes = {n: _fn(r, f"runtime '{n}'", required=True) for n, r in self.runtime_refs.items()}
        topo = self.topology

        class _SpecTeam:              # run_team_async only needs .build()
            def build(self_):
                return topo

        res = await run_team_async(_SpecTeam(), self.task, leader_fn, runtimes, self.team_dir,
                                   max_steps=self.max_steps)
        ctx = dict(context) if context else {}
        ctx["team_result"] = res
        ctx["output"] = res.get("report") or res.get("error") or ""
        return LinkResult(status=LinkStatus.SUCCESS if res.get("ok") else LinkStatus.ERROR,
                          context=ctx, error=res.get("error"))

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'team_run "{self.name}" [LEADER-DRIVEN] → ' + self.topology.describe(0).lstrip()


def _team_run_op(s: dict) -> Link:
    """Op: run the topology as a LEADER-DRIVEN team. `topology`=a spec of AgentRefs; `leader`=a
    register_fn'd runtime (or LeaderFn if leader_mode='raw'); `runtimes`={agent: register_fn name}."""
    team_dir = s.get("team_dir") or str(_cave_dir("runs") / s.get("name", "team_run"))
    return _TeamRunLink(_build(s["topology"]), s.get("task", ""), team_dir,
                        s.get("leader"), s.get("runtimes", {}),
                        leader_mode=s.get("leader_mode", "llm"), max_steps=s.get("max_steps", 40),
                        name=s.get("name", "team_run"))


register("team_run", _team_run_op)


# NOT cave() build-ops, by nature:
#   `evolve` — a genetic FILESYSTEM op (returns child dirs, not a Link)
#   `conditions`/Harness — the message state-machine, a separate runtime axis (composed by team_run)
# Both stay native-API utilities you call directly.


# ── the golden library (quarantine → golden), project-local under .cave/ ──────
def _cave_dir(sub: str) -> Path:
    d = Path(os.environ.get("CAVE_HOME", ".cave")) / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def _quarantine(name: str, spec: dict) -> str:
    p = _cave_dir("quarantine") / f"{name}.json"
    p.write_text(json.dumps(spec, indent=2))
    return str(p)


def _goldenize(name: str) -> dict:
    """Promote a quarantined spec → golden. HUMAN-gated: calling this IS the approval."""
    q = _cave_dir("quarantine") / f"{name}.json"
    if not q.exists():
        return {"status": "error", "error": f"no quarantined team named '{name}'"}
    g = _cave_dir("golden") / f"{name}.json"
    g.write_text(q.read_text())
    q.unlink()
    return {"status": "goldenized", "name": name, "path": str(g)}


def _golden_search(query: str) -> List[dict]:
    out = []
    for f in _cave_dir("golden").glob("*.json"):
        text = f.read_text()
        if query.lower() in text.lower():
            out.append({"name": f.stem, "spec": json.loads(text)})
    return out


def _load_golden(name: str) -> dict:
    p = _cave_dir("golden") / f"{name}.json"
    if not p.exists():
        known = [f.stem for f in _cave_dir("golden").glob("*.json")]
        raise KeyError(f"no golden team '{name}' — golden library: {known}")
    return json.loads(p.read_text())


# Goldenizing EXTENDS the metacontrol surface: a goldenized team is now a callable op.
#   {"op":"golden","name":"research_crew"}  ← drops a proven team into any bigger spec.
register("golden", lambda s: _build(_load_golden(s["name"])))


def golden(name: str) -> Link:
    """Load a goldenized (proven) team as a native Link — reuse it in the DSL like any agent:
        release = planner >> golden("ship_crew") >> publish"""
    return _build(_load_golden(name))


# ── boundaried discovery: scan for cave team specs across given roots ──────────
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv",
              "dist", "build", ".next", ".pytest_cache"}


def _cave_summary(project: Path, cave: Path) -> dict:
    def names(sub: str) -> List[str]:
        d = cave / sub
        return sorted(f.stem for f in d.glob("*.json")) if d.is_dir() else []
    return {"project": str(project), "cave": str(cave),
            "golden": names("golden"), "quarantine": names("quarantine")}


def scan_caves(roots: Optional[List[str]] = None, recursive: bool = True) -> List[dict]:
    """Find every `.cave` PROJECT across the given BOUNDARIES.

    The project-level discovery a GLOBAL cave (a separate app) uses to enumerate / federate all
    cave-enabled projects: each hit is a directory that has a `.cave/`, reported with its contents
    (golden + quarantine team names). roots ARE the boundary; heavy dirs are pruned and `.cave` is
    not descended into. Pair with a global `.cave` to index every project's golden teams centrally.

    returns: [{"project","cave","golden":[...],"quarantine":[...]}]
    """
    import os
    out: List[dict] = []
    for root in (roots or ["."]):
        rp = Path(root)
        if not rp.exists():
            continue
        if recursive:
            for dirpath, dirnames, _files in os.walk(rp):
                if ".cave" in dirnames:
                    out.append(_cave_summary(Path(dirpath), Path(dirpath) / ".cave"))
                dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and d != ".cave"]  # prune + don't descend .cave
        else:
            if (rp / ".cave").is_dir():
                out.append(_cave_summary(rp, rp / ".cave"))
    return out


def scan_library(roots: Optional[List[str]] = None, kind: str = "golden",
                 recursive: bool = True) -> List[dict]:
    """Discover cave team specs across the given BOUNDARIES.

    roots:     the directories that bound the search (default ['.']). Each is scanned for
               `.cave/<kind>/*.json`; with recursive=True, nested `.cave/` dirs anywhere under a
               root are found too — so a workspace of projects surfaces all its golden teams.
               Heavy dirs (node_modules/.git/…) are pruned. The roots ARE the boundary: nothing
               outside them is touched.
    kind:      'golden' | 'quarantine'.
    returns:   [{"name","path","root","kind"}].
    """
    import os
    found: List[dict] = []
    for root in (roots or ["."]):
        rp = Path(root)
        if not rp.exists():
            continue
        if recursive:
            for dirpath, dirnames, _files in os.walk(rp):
                dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]  # prune the walk
                kd = Path(dirpath) / ".cave" / kind
                if kd.is_dir():
                    found += [{"name": f.stem, "path": str(f), "root": str(rp), "kind": kind}
                              for f in kd.glob("*.json")]
        else:
            kd = rp / ".cave" / kind
            if kd.is_dir():
                found += [{"name": f.stem, "path": str(f), "root": str(rp), "kind": kind}
                          for f in kd.glob("*.json")]
    return found


# ── the metacontrol function ──────────────────────────────────────────────────
async def cave(
    spec: Any = None,
    *,
    name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    execute: bool = True,
    save: bool = False,
    goldenize: bool = False,
    describe_only: bool = False,
    search: Optional[str] = None,
) -> dict:
    """Drive the whole native API from one door. Phases compose; never throws.

    search=<q>            → substring search over the golden library (reuse a proven team)
    goldenize=True,name=  → promote quarantine → golden (human approval = this call)
    save=True             → write the spec to .cave/quarantine/
    describe_only=True    → build + describe, do not run
    execute=True (default)→ build + run, return the run envelope
    """
    if search is not None:
        return {"status": "ok", "query": search, "matches": _golden_search(search)}

    if goldenize:
        if not name:
            return {"status": "error", "error": "name required to goldenize"}
        return _goldenize(name)

    # construction
    try:
        link = _build(spec)
    except (KeyError, TypeError, ValueError) as e:
        op = spec.get("op") if isinstance(spec, dict) else "?"
        return {"status": "construction_error", "error": str(e),
                "hint": f"read the cave-{op} skill"}

    nm = name or getattr(link, "name", "team")
    if save:
        _quarantine(nm, spec)

    if describe_only:
        return {"status": "described", "name": nm, "description": link.describe(), "spec": spec}

    if execute:
        try:
            res = await link.execute(context or {})
        except Exception as e:  # runtime, distinct from construction
            return {"status": "runtime_error", "name": nm, "error": str(e)}
        return {"status": res.status.value, "name": nm, "context": res.context, "error": res.error}

    return {"status": "built", "name": nm}
