"""
workflow.py — Workflow-tool parity primitives for cave_teams (the concurrency / orchestration plane).

The SDNA chain ontology gave us a sequential Chain; cave_teams added ConcurrentChain (barrier fan-out).
This closes the remaining gaps vs the Claude Code Workflow tool (see SDNA-WORKFLOW-PARITY):

  pipeline(items, *stages)    — NO-BARRIER streaming: item A can be in stage 3 while B is in stage 1.
                                Wall-clock = slowest single-item chain, not sum-of-slowest-per-stage.
  parallel(thunks)            — barrier fan-out with a concurrency CAP (a throwing thunk → None).
  run_until(step, predicate)  — loop a step until a predicate holds (bounded).
  Memo / content_key          — content-hash resume (same input → cached result, thunk not re-run).
  with_schema(thunk, valid)   — forced structured output (validate + retry), like the Workflow schema opt.

All async, all stdlib. Concurrency is capped by a shared semaphore (Workflow caps at ~min(16, cores-2)).
NOTE: `pipeline` here is the streaming items-primitive — distinct from `topologies.pipeline` (a sequential
Chain of Links); reach it as `cave_teams.workflow.pipeline`.
"""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
from typing import Any, Callable, List, Sequence

CONCURRENCY = 8  # default cap (Workflow ≈ min(16, cores-2))


async def _maybe_await(v):
    return await v if inspect.isawaitable(v) else v


async def parallel(thunks: Sequence[Callable[[], Any]], concurrency: int = CONCURRENCY) -> List[Any]:
    """Barrier fan-out, capped. thunk = () -> (value | awaitable). A throwing thunk → None (filter with
    Boolean before use). Results in input order. (= Workflow parallel().)"""
    sem = asyncio.Semaphore(concurrency)

    async def run(thunk):
        async with sem:
            try:
                return await _maybe_await(thunk())
            except Exception:
                return None

    return await asyncio.gather(*[run(t) for t in thunks])


async def pipeline(items: Sequence[Any], *stages: Callable[[Any, Any, int], Any],
                   concurrency: int = CONCURRENCY) -> List[Any]:
    """Per-item streaming through stages — NO barrier between stages. Each stage = fn(prev, item, index)
    -> (value | awaitable). Up to `concurrency` items in flight; each runs its stages in order, but item
    B does not wait for item A to advance. A stage that throws drops that item to None. (= Workflow
    pipeline().)"""
    sem = asyncio.Semaphore(concurrency)

    async def run_item(item, idx):
        async with sem:
            cur = item
            for stage in stages:
                try:
                    cur = await _maybe_await(stage(cur, item, idx))
                except Exception:
                    return None
            return cur

    return await asyncio.gather(*[run_item(it, i) for i, it in enumerate(items)])


async def run_until(step: Callable[[int], Any], predicate: Callable[[Any], bool],
                    max_iters: int = 10) -> dict:
    """Loop step(i) -> (value | awaitable) until predicate(result) is truthy, or max_iters. Returns
    {result, iters, satisfied}. (= Workflow loop-until pattern; bounded so it always halts.)"""
    result = None
    for i in range(max_iters):
        result = await _maybe_await(step(i))
        if predicate(result):
            return {"result": result, "iters": i + 1, "satisfied": True}
    return {"result": result, "iters": max_iters, "satisfied": False}


def content_key(*parts: Any) -> str:
    """Stable content hash of the inputs (for resume / memoization)."""
    h = hashlib.sha256()
    for p in parts:
        h.update(json.dumps(p, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


class Memo:
    """Content-hash cache for resume: same key → cached result, thunk not re-run."""

    def __init__(self):
        self.store: dict = {}
        self.hits = 0
        self.misses = 0

    async def call(self, key: str, thunk: Callable[[], Any]) -> Any:
        if key in self.store:
            self.hits += 1
            return self.store[key]
        self.misses += 1
        r = await _maybe_await(thunk())
        self.store[key] = r
        return r


class SchemaError(Exception):
    pass


async def with_schema(thunk: Callable[[], Any], validate: Callable[[Any], bool], retries: int = 2) -> Any:
    """Run thunk; validate(result) must be truthy (else retry). Up to `retries` extra attempts. Mirrors
    the Workflow schema option (forced structured output that retries on mismatch)."""
    last = None
    for _ in range(retries + 1):
        r = await _maybe_await(thunk())
        try:
            if validate(r):
                return r
            last = "validator returned falsy"
        except Exception as e:
            last = e
    raise SchemaError(f"output failed validation after {retries + 1} tries: {last}")


__all__ = ["pipeline", "parallel", "run_until", "Memo", "content_key", "with_schema",
           "SchemaError", "CONCURRENCY"]
