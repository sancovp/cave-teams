"""
algebra.py — the agent-composition ALGEBRA over Links (Phase 3).

Carrier  A = Links — anything with `execute(context) -> LinkResult` (AgentLink, TeamRuntime, SDNAC,
as_link(heaven/callable), and every composition below). A Link is a state-transformer over the shared
context: a Kleisli-ish arrow  context ↦ (status, context).

Operators (the signature of the algebra):

    skip()                  1    identity — passes the context through (unit of ; and ∥)
    seq(a, b, …)            ;    sequential composition (Chain) — run in order, thread the context
    par(a, b, …)            ∥    parallel composition (ConcurrentChain) — run concurrently, merge
    choice([(g,a)…], d)     +    guarded choice (Router) — run the first a whose guard g(ctx) holds
    gate(body, φ, …)        μ    bounded fixpoint to an evaluator gate (EvalChain) — loop until φ approves
    dovetail(a, D, b)       ⋈    typed data-flow joint (DovetailModel) — a ; transform(D) ; b
    lift(obj)               ⟦·⟧  embed any runnable (heaven/callable/.send) into A
    team(G, name)                present a composition G as ONE Link (the homoiconic closure)

A is CLOSED under every operator (a Chain IS a Link) — the homoiconic law agent = team = agent.
The equational theory is in LAWS.md and is MECHANICALLY VERIFIED in test_algebra_laws.py (the laws are
the first agent proofs). seq/par/gate/choice alias the topology builders; this module is the algebraic
naming + skip/dovetail/team.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from .chain_ontology import Chain, Link, LinkResult, LinkStatus
from .concurrent import ConcurrentChain
from .topologies import pipeline as _seq, fan_out as _par, eval_chain as _gate, router as _choice
from .sdna_bridge import as_link as lift  # noqa: F401  (⟦·⟧ — embed any runnable)
from .dovetail import DovetailModel


# ── 1  identity ────────────────────────────────────────────────────────────
class Skip(Link):
    """Identity Link — the context passes through unchanged. Unit of ; and ∥."""
    name = "skip"

    def __init__(self, name: str = "skip"):
        self.name = name

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        return LinkResult(status=LinkStatus.SUCCESS, context=dict(context) if context else {})

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + "Skip (1)"


def skip() -> Skip:
    return Skip()


# ── ; sequential, ∥ parallel, + choice, μ gate ──────────────────────────────
def seq(*links: Link, name: str = "seq") -> Chain:
    """a ; b ; … — sequential composition."""
    return _seq(*links, name=name)


def par(*links: Link, name: str = "par") -> ConcurrentChain:
    """a ∥ b ∥ … — parallel composition."""
    return _par(*links, name=name)


def choice(routes: List[Tuple[Callable[[Dict[str, Any]], bool], Link]],
           default: Optional[Link] = None, name: str = "choice"):
    """a + b — guarded choice (first guard that holds)."""
    return _choice(routes, default=default, name=name)


def gate(body: Link, phi: Link, max_cycles: int = 3,
         approval_key: str = "approved", name: str = "gate"):
    """μ — bounded fixpoint: run body, then evaluator φ; loop until φ sets ctx[approval_key] or max_cycles."""
    return _gate(body, phi, max_cycles=max_cycles, approval_key=approval_key, name=name)


# ── ⋈ dovetail (typed data-flow joint) ──────────────────────────────────────
class _DovetailTransform(Link):
    """The joint itself: apply a DovetailModel to the context (load files, validate, extract named
    inputs) between two Links. Errors (missing expected_outputs) surface as a BLOCKED/ERROR Link."""

    def __init__(self, name: str, model: DovetailModel):
        self.name = name
        self.model = model

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx = dict(context) if context else {}
        try:
            ctx.update(self.model.prepare_next_inputs(ctx))
        except ValueError as e:
            return LinkResult(status=LinkStatus.ERROR, context=ctx, error=str(e))
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'Dovetail "{self.model.name or self.name}" (⋈)'


def dovetail(a: Link, model: DovetailModel, b: Link, name: str = "dovetail") -> Chain:
    """a ⋈[D] b  ≡  a ; transform(D) ; b — the typed data-flow joint between two Links."""
    return seq(a, _DovetailTransform(f"{name}:joint", model), b, name=name)


# ── team — present a composition as one Link (homoiconic closure) ───────────
class Subgraph(Link):
    """Wrap a composition G as ONE named Link (G is already a Link; this gives it its own identity).
    run(team(G)) ≡ run(G) — the closure law (agent = team = agent)."""

    def __init__(self, name: str, inner: Link):
        self.name = name
        self.inner = inner

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        return await self.inner.execute(context)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'team "{self.name}" ⟶ ' + self.inner.describe(0).lstrip()


def team(G: Link, name: str = "team") -> Subgraph:
    return Subgraph(name, G)


__all__ = [
    "skip", "Skip", "seq", "par", "choice", "gate", "dovetail", "lift", "team", "Subgraph",
]
