"""
topologies.py — the topology menu, built ON the chain ontology (NOT a parallel SDNA).

Every topology here returns a composed `Link` (a `Chain` / `ConcurrentChain` / `EvalChain` / `Router`
of sub-Links) that you `await ...execute(context)`. Leaves are Links (AgentLink, TeamRuntime,
ConfigLink, or — Phase 2 — SDNA SDNAC/heaven Links). Because a Chain IS a Link, everything nests.

This is the chain-ontology-native rebuild: `chain`/`eval_chain`/`duo` are now literally `Chain`/
`EvalChain` of Links (no reimplementation). Beyond-chain, condition-gated message-passing graphs live
on the Harness (cave_teams.harness + cave_teams.conditions); a Harness team is a Link (TeamRuntime), so
those nest into the ontology too.

Context convention (see links.py): each Link reads its input from the previous link's `output` and
writes its reply to `output`; Dovetail overrides with typed named inputs when needed.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .chain_ontology import Chain, EvalChain, Link, LinkResult, LinkStatus
from .concurrent import ConcurrentChain


# ───────────────────────────────────────────────────────────── sequential / parallel
def pipeline(*links: Link, name: str = "pipeline") -> Chain:
    """Sequential A→B→C — SDNA Chain. Each link's `output` feeds the next."""
    return Chain(name, list(links))


# `chain` IS the SDNA Chain (homoiconic): a Chain of Links, where a Link may itself be a Chain.
chain = pipeline


def fan_out(*links: Link, name: str = "fan_out") -> ConcurrentChain:
    """Scatter — run all links in PARALLEL on the same input (ConcurrentChain)."""
    return ConcurrentChain(name, list(links))


broadcast = fan_out


def synthesis_gate(workers: List[Link], reducer: Link, name: str = "synthesis") -> Chain:
    """Scatter-gather / map-reduce: run `workers` in parallel, then `reducer` over the merged context.
    The reducer sees every worker's output (output:<worker> keys + the `_concurrent` list)."""
    return Chain(name, [ConcurrentChain(f"{name}:scatter", list(workers)), reducer])


map_reduce = synthesis_gate


def tournament(competitors: List[Link], judge: Link, name: str = "tournament") -> Chain:
    """The CC-teams tree-search pattern: N competitors craft in parallel, a JUDGE selects the best.
    = map_reduce with the reducer being a judge/argmax. In the crafter-sim the judge is the USER's
    purchase (the sound external gate). For multi-round, wrap in eval_chain; for hierarchical, nest."""
    return synthesis_gate(competitors, judge, name=name)


# ───────────────────────────────────────────────────────────── evaluator loops (OVP / DUO)
def eval_chain(body: Link, evaluator: Link, max_cycles: int = 3,
               approval_key: str = "approved", name: str = "eval_chain") -> EvalChain:
    """SDNA EvalChain — run `body`, then `evaluator`; loop until the evaluator sets
    context[approval_key] truthy, or max_cycles. `body` may be a single Link or a Chain."""
    links = list(body.links) if isinstance(body, Chain) else [body]
    return EvalChain(name, links, evaluator=evaluator, max_cycles=max_cycles, approval_key=approval_key)


def loop_refine(worker: Link, critic: Link, max_cycles: int = 3,
                approval_key: str = "approved", name: str = "loop_refine") -> EvalChain:
    """Reflection loop: worker drafts, critic evaluates; repeat until the critic approves."""
    return eval_chain(worker, critic, max_cycles=max_cycles, approval_key=approval_key, name=name)


def duo(ariadne: Link, poimandres: Link, ovp: Link, max_cycles: int = 3,
        approval_key: str = "approved", name: str = "duo") -> EvalChain:
    """SDNA DUOChain shape — A (Ariadne) → P (Poimandres) inner chain, OVP evaluator loop until approved."""
    return EvalChain(name, [ariadne, poimandres], evaluator=ovp,
                     max_cycles=max_cycles, approval_key=approval_key)


def round_robin(links: List[Link], rounds: int = 1, name: str = "round_robin") -> Chain:
    """Turn-taking — the links in sequence, repeated `rounds` times."""
    seq: List[Link] = []
    for _ in range(rounds):
        seq.extend(links)
    return Chain(name, seq)


# ───────────────────────────────────────────────────────────── conditional routing (branch)
class Router(Link):
    """Conditional branch: run the first (predicate, link) whose predicate(context) is True, else
    `default`. Predicates are plain Python over the context dict — the open, Turing-complete branch."""

    def __init__(self, name: str, routes: List[Tuple[Callable[[Dict[str, Any]], bool], Link]],
                 default: Optional[Link] = None):
        self._name = name
        self.routes = routes
        self.default = default

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx = dict(context) if context else {}
        guard_errors = []
        for i, (pred, link) in enumerate(self.routes):
            try:
                hit = pred(ctx)
            except Exception as e:
                # a RAISING guard is not the same as a False guard — record it so a broken
                # predicate (KeyError on a missing ctx field, …) is visible, then keep routing
                guard_errors.append({"route": i, "link": getattr(link, "name", "?"), "error": str(e)})
                continue
            if hit:
                if guard_errors:
                    ctx["_router_errors"] = guard_errors
                return await link.execute(ctx)
        if guard_errors:
            ctx["_router_errors"] = guard_errors
        if self.default is not None:
            return await self.default.execute(ctx)
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def describe(self, depth: int = 0) -> str:
        indent = "  " * depth
        lines = [f'{indent}Router "{self.name}" ({len(self.routes)} branches):']
        for _, link in self.routes:
            lines.append(f"{indent}  ├── ? {link.describe(depth + 1).lstrip()}")
        if self.default is not None:
            lines.append(f"{indent}  └── default {self.default.describe(depth + 1).lstrip()}")
        return "\n".join(lines)


def router(routes: List[Tuple[Callable[[Dict[str, Any]], bool], Link]],
           default: Optional[Link] = None, name: str = "router") -> Router:
    """Build a conditional-branch Link from (predicate, link) pairs."""
    return Router(name, routes, default)


# supervisor = a router/Chain driven by a lead Link; left as a composition the caller builds
# (lead Link whose output routes via a Router). Documented, not a separate primitive.


# ───────────────────────────────────────────────────────────── SDNA ChainTool JSON → ontology
def chain_from_spec(spec: Dict[str, Any], leaf_factory: Optional[Callable[[Dict[str, Any]], Link]] = None) -> Link:
    """Lower an SDNA ChainTool JSON spec (config_link / chain / eval_chain) onto the REAL ontology.

    config_link → a leaf Link (default: AgentLink from name/system_prompt/model); chain → Chain;
    eval_chain → EvalChain (its `evaluator` config_link is the evaluator). Pass `leaf_factory` to
    control how a config_link becomes a runnable Link (e.g. an SDNA SDNAC in Phase 2).
    """
    if leaf_factory is None:
        from .links import AgentLink

        def leaf_factory(cfg: Dict[str, Any]) -> Link:  # noqa: F811
            model = cfg.get("model") or ""
            backend = "claude-p" if any(m in str(model).lower() for m in ("claude", "opus", "sonnet", "haiku")) else "minimax"
            return AgentLink(cfg.get("name", "agent"), system_prompt=cfg.get("system_prompt", ""),
                             backend=backend, model=model or None)

    t = spec.get("type")
    if t == "config_link":
        return leaf_factory(spec)
    if t == "chain":
        return Chain(spec.get("name", "chain"),
                     [chain_from_spec(lk, leaf_factory) for lk in spec.get("links", [])])
    if t == "eval_chain":
        body = spec.get("chain") or {"type": "chain", "name": spec.get("name", "eval"), "links": spec.get("links", [])}
        body_link = chain_from_spec(body, leaf_factory)
        links = list(body_link.links) if isinstance(body_link, Chain) else [body_link]
        evaluator = leaf_factory(spec["evaluator"]) if spec.get("evaluator") else None
        return EvalChain(spec.get("name", "eval_chain"), links, evaluator=evaluator,
                         max_cycles=spec.get("max_cycles", 3),
                         approval_key=spec.get("approval_key", "approved"))
    raise ValueError(f"unsupported chain_spec type: {t!r}")


__all__ = [
    "pipeline", "chain", "fan_out", "broadcast", "synthesis_gate", "map_reduce", "tournament",
    "eval_chain", "loop_refine", "duo", "round_robin", "Router", "router", "chain_from_spec",
]
