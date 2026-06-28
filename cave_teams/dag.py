"""
dag.py — the general partial-order scheduler over Links (the team `blockedBy` topology).

`seq` (total order) and `par` (empty order) are the two LIMITS of a partial order; the general case is a
dependency DAG — CC-teams' `TaskCreate(blockedBy=[...])`. `dag(nodes, deps)` runs each node as soon as
all its dependencies are done; independent nodes run concurrently. A node's input context = the initial
context folded with each of its dependencies' output contexts (dataflow along the edges). The result is a
`Link`, so a DAG composes/nests like any other.

Limits (verified in test_dag_smoke.py):
  dag with linear deps  (a→b→c)   ≡  seq(a, b, c)
  dag with no deps      ({})       ≡  par(a, b, c)
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional, Tuple, Union

from .chain_ontology import Link, LinkResult, LinkStatus


class DagChain(Link):
    """A dependency DAG of Links. nodes: {name: Link}; deps: {name: [prereq names]}."""

    def __init__(self,
                 nodes: Union[Dict[str, Link], List[Tuple[str, Link]]],
                 deps: Optional[Dict[str, List[str]]] = None,
                 name: str = "dag"):
        self.nodes: Dict[str, Link] = dict(nodes)
        deps = deps or {}
        self.deps: Dict[str, List[str]] = {n: list(deps.get(n, [])) for n in self.nodes}
        self.name = name
        # validate: every dependency names a real node
        for n, ds in self.deps.items():
            for d in ds:
                if d not in self.nodes:
                    raise ValueError(f"dag: node {n!r} depends on unknown node {d!r}")

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx0 = dict(context) if context else {}
        outputs: Dict[str, Dict[str, Any]] = {}     # name -> its output context
        statuses: Dict[str, str] = {}
        done: set = set()
        remaining: set = set(self.nodes)

        async def run_node(n: str):
            inp = dict(ctx0)
            for d in self.deps[n]:                  # fold each dependency's output (dataflow along edges)
                inp.update(outputs[d])
            return n, await self.nodes[n].execute(inp)

        while remaining:
            ready = [n for n in remaining if all(d in done for d in self.deps[n])]
            if not ready:                           # nothing runnable ⇒ a cycle (or unreachable set)
                return LinkResult(status=LinkStatus.ERROR, context=ctx0,
                                  error=f"dag: cycle or unsatisfiable dependencies among {sorted(remaining)}")
            settled = await asyncio.gather(*[run_node(n) for n in ready])
            for n, r in settled:
                statuses[n] = getattr(r.status, "value", str(r.status))
                if r.status != LinkStatus.SUCCESS:  # a failed node halts the DAG, carrying its status up
                    return LinkResult(status=r.status, context=r.context,
                                      error=f"dag node {n!r}: {r.error}")
                outputs[n] = r.context if r.context else {}
                done.add(n)
                remaining.discard(n)

        final = dict(ctx0)                          # merge all node outputs (later-completed win, like ∥)
        for n in self.nodes:
            final.update(outputs.get(n, {}))
        final["_dag"] = statuses
        return LinkResult(status=LinkStatus.SUCCESS, context=final)

    def describe(self, depth: int = 0) -> str:
        pad = "  " * depth
        lines = [f'{pad}dag "{self.name}" ({len(self.nodes)} nodes):']
        for n in self.nodes:
            ds = self.deps[n]
            edge = f" ← {', '.join(ds)}" if ds else " (root)"
            lines.append(f"{pad}  {n}{edge}")
        return "\n".join(lines)


def dag(nodes: Union[Dict[str, Link], List[Tuple[str, Link]]],
        deps: Optional[Dict[str, List[str]]] = None,
        name: str = "dag") -> DagChain:
    """Build a dependency-DAG Link. `seq` and `par` are its limits (linear deps / no deps)."""
    return DagChain(nodes, deps, name=name)


__all__ = ["dag", "DagChain"]
