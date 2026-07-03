"""
wiring.py — compile a topology (the algebra) into message-flow EDGES (rule 03 -> rule 01).

This is the bridge: the algebra (seq/par/choice/gate/team over agents) describes the topology;
`compile_to_edges` walks that structure and emits `Edge`s whose conditions are conditions-on-
messages (after-agent join/barrier). The leaves are `AgentRef`s — references to cave agents by
name (agents are cave's; cave-teams only references them).

So: a Chain of agents => sequential after-edges; a ConcurrentChain => parallel edges; a team
(Subgraph) => its inner composition inlined. The Link is the authoring form; edges are what the
CHECK/LIFT runtime (flow.py) executes over the team messages dir.
"""
from __future__ import annotations

from typing import List, Tuple

from .chain_ontology import Link, Chain
from .concurrent import ConcurrentChain
from .algebra import Subgraph
from .flow import Edge, Condition, after, always


class AgentRef(Link):
    """A leaf = a reference to a cave agent by name. Its 'execution' in the cave-teams sense
    is 'dispatch to the cave agent named `name`' — the cave agent actually runs it."""

    def __init__(self, name: str):
        self.name = name

    async def execute(self, context=None, **kwargs):  # pragma: no cover - not run in-process here
        raise NotImplementedError("AgentRef is dispatched to a cave agent, not executed in-process")

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f"agent:{self.name}"


def _compile(link: Link, entry: List[Condition]) -> Tuple[List[Edge], List[str]]:
    """Return (edges, exit_agents). `entry` gates the first dispatch(es) of this subtree;
    `exit_agents` are who must respond before a following sibling may fire."""
    from .algebra import Subgraph, Skip, _DovetailTransform
    from .links import AgentLink
    from .topologies import Router
    from .chain_ontology import EvalChain

    if isinstance(link, (AgentRef, AgentLink)):    # a leaf agent — one edge
        return [Edge(to=link.name, conditions=list(entry))], [link.name]

    if isinstance(link, Subgraph):                 # team(G): inline the inner composition
        return _compile(link.inner, entry)

    if isinstance(link, (Skip, _DovetailTransform)):
        # identity / ctx-transform joints are TRANSPARENT to message flow: no agent to dispatch,
        # no exit to wait on (a seq keeps threading the previous exits through them).
        return [], []

    if isinstance(link, EvalChain):
        # NOTE ordering: EvalChain IS-A Chain — this check must precede the Chain branch, or the
        # evaluator + loop would silently compile away (the old phantom-agent bug).
        raise TypeError(
            f"cannot compile gate/eval_chain '{link.name}' into leader-driven edges: the evaluator "
            f"loop has no edge representation. Run it in-process (await link.execute / cave()), or "
            f"express the iteration as leader open_rules and let the leader re-dispatch.")

    if isinstance(link, Router):
        raise TypeError(
            f"cannot compile choice/router '{link.name}' into leader-driven edges: branching is the "
            f"LEADER's decision in a team run. Give the leader the branch rule as an open_rule, or "
            f"run the Router in-process (await link.execute / cave()).")

    if isinstance(link, ConcurrentChain):          # par: all children share the same entry gate
        edges: List[Edge] = []
        exits: List[str] = []
        for child in link.links:
            ce, cx = _compile(child, entry)
            edges += ce
            exits += cx
        return edges, exits

    if isinstance(link, Chain):                    # seq: each child waits for the previous exits
        edges = []
        conds = list(entry)
        exits = []
        for child in link.links:
            ce, cx = _compile(child, conds)
            edges += ce
            conds = [after(*cx)] if cx else conds
            exits = cx
        return edges, exits

    if hasattr(link, "build") and callable(link.build):   # a Team used as a node: inline its topology
        return _compile(link.build(), entry)

    # No silent fallback: an unknown Link must not become a phantom agent (an edge to a name that
    # can never respond permanently blocks every downstream teammate).
    raise TypeError(
        f"cannot compile {type(link).__name__} {getattr(link, 'name', '')!r} into message edges — "
        f"leaves must be AgentRef/AgentLink (or a Team/Subgraph/seq/par of them)")


def compile_to_edges(topology: Link) -> List[Edge]:
    """Compile an algebra composition into the edges the CHECK/LIFT runtime executes."""
    edges, _ = _compile(topology, [always()])
    return edges
