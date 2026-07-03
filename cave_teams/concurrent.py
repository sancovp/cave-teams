"""
concurrent.py — ConcurrentChain: the cave-teams contribution to the chain ontology.

SDNA's `Chain` runs its links SEQUENTIALLY (its one structural gap). `ConcurrentChain(Chain)` runs them
in PARALLEL — each link gets a COPY of the incoming context, all run via asyncio.gather, and their
results are merged back. This is fan-out / scatter at the ONTOLOGY level (a Chain that is also a Link,
so it still composes and nests). Blocking leaves (an LLM subprocess) should `await asyncio.to_thread(...)`
inside their execute() to get real wall-clock parallelism; async leaves run concurrently as-is.
"""

from __future__ import annotations

import asyncio
import copy
from typing import Any, Dict, Optional

from .chain_ontology import Chain, Link, LinkResult, LinkStatus


def _branch_ctx(base: Dict[str, Any]) -> Dict[str, Any]:
    """A per-branch copy of the context. DEEP where possible — a shallow dict() shares every nested
    mutable (lists/dicts) across concurrently-running branches, so one branch's in-place mutation
    races every other. Falls back to shallow only for un-deepcopyable values (live runtimes etc.)."""
    try:
        return copy.deepcopy(base)
    except Exception:
        return dict(base)


class ConcurrentChain(Chain):
    """A Chain whose links run CONCURRENTLY (fan-out) instead of sequentially.

    Merge policy: start from the incoming context; fold in each link's NEW or changed keys (later
    links win on a genuine conflict); every link's full result context is also collected under the
    `_concurrent` key (a list, in link order). If any link errors/blocks, the first such status is
    returned (with the merged context); otherwise SUCCESS.
    """

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        base: Dict[str, Any] = dict(context) if context else {}
        if not self.links:
            return LinkResult(status=LinkStatus.SUCCESS, context=base)

        results = await asyncio.gather(
            *[link.execute(_branch_ctx(base)) for link in self.links],
            return_exceptions=True,
        )

        merged: Dict[str, Any] = dict(base)
        collected = []
        failure: Optional[LinkResult] = None

        for r in results:
            if isinstance(r, BaseException):
                collected.append({"error": str(r)})
                if failure is None:
                    failure = LinkResult(status=LinkStatus.ERROR, context=merged, error=str(r))
                continue
            collected.append(r.context)
            for k, v in r.context.items():
                if k not in base or base.get(k) != v:
                    merged[k] = v
            if r.status != LinkStatus.SUCCESS and failure is None:
                failure = LinkResult(status=r.status, context=merged, error=r.error)

        merged["_concurrent"] = collected
        if failure is not None:
            failure.context = merged
            return failure
        return LinkResult(status=LinkStatus.SUCCESS, context=merged)

    def describe(self, depth: int = 0) -> str:
        indent = "  " * depth
        lines = [f"{indent}ConcurrentChain \"{self.name}\" ({len(self.links)} links, parallel):"]
        for i, link in enumerate(self.links):
            connector = "└──" if i == len(self.links) - 1 else "├──"
            child = link.describe(depth + 1).lstrip()
            lines.append(f"{indent}  {connector} ∥ {child}")
        return "\n".join(lines)
