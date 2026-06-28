"""
dsl.py — literal algebra NOTATION over Links (Phase 4).

Importing cave_teams installs operator notation on the Link class, so an agent runtime is written as an
algebraic EXPRESSION that lowers to the chain ontology + cave-teams runtime:

    a >> b            sequential   ;    = seq(a, b)
    a | b             parallel     ∥    = par(a, b)
    a >> dove(D) >> b typed joint  ⋈    (D is a DovetailModel)
    gate(body, phi)   fixpoint     μ    · choice([...]) + · lift(obj) ⟦·⟧ · team(G)

`>>` and `|` FLATTEN a plain Chain / ConcurrentChain so the lowered tree stays flat; the
associativity/identity laws (LAWS.md) make this sound. Example:

    flow = research >> (critic | factcheck) >> dove(D) >> writer
    await flow.execute({"goal": "..."})

The notation is additive (it only adds __rshift__/__or__ to Link); it does not change execution.
"""

from __future__ import annotations

from .chain_ontology import Chain, Link
from .concurrent import ConcurrentChain
from .algebra import _DovetailTransform
from .dovetail import DovetailModel


def dove(model: DovetailModel, name: str = "dovetail") -> Link:
    """The ⋈ joint as a Link: `a >> dove(D) >> b` applies the Dovetail D between a and b."""
    return _DovetailTransform(f"{name}:joint", model)


def _rshift(self: Link, other: Link):
    """a >> b  ≡  a ; b. Flattens plain Chains on BOTH sides into a normal-form flat Chain, so
    associativity is a STRUCTURAL identity: (a>>(b>>c)).links == ((a>>b)>>c).links == [a,b,c].
    (Only a plain Chain flattens — EvalChain/ConcurrentChain keep their boundary; use team(...) to
    force a nested sub-chain.)"""
    left = list(self.links) if type(self) is Chain else [self]
    right = list(other.links) if type(other) is Chain else [other]
    return Chain("seq", left + right)


def _or(self: Link, other: Link):
    """a | b  ≡  a ∥ b. Flattens plain ConcurrentChains on BOTH sides into one flat ConcurrentChain
    (∥ is a commutative monoid — flat normal form)."""
    left = list(self.links) if type(self) is ConcurrentChain else [self]
    right = list(other.links) if type(other) is ConcurrentChain else [other]
    return ConcurrentChain("par", left + right)


def install() -> None:
    """Install the >> and | notation on the shared Link class (idempotent, additive)."""
    if getattr(Link, "_cave_teams_dsl", False):
        return
    Link.__rshift__ = _rshift
    Link.__or__ = _or
    Link._cave_teams_dsl = True


# install on import (cave_teams.__init__ imports this) — additive, does not change execution
install()
