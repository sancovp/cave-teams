#!/usr/bin/env python3
"""Workflow-parity primitives. NO API.
Headline: pipeline STREAMS (no barrier) — proven by a deadlock-if-barrier construction."""
import asyncio

from cave_teams.workflow import pipeline, parallel, run_until, Memo, content_key, with_schema, SchemaError


async def main():
    # pipeline correctness — each item through every stage in order
    async def dbl(x, item, i):
        return x * 2

    async def inc(x, item, i):
        return x + 1

    assert await pipeline([1, 2, 3], dbl, inc) == [3, 5, 7]
    print("  pipeline   items flow through stages ✓")

    # pipeline STREAMING (no barrier): item0 cannot leave stage1 until SOME item reaches stage2.
    # If pipeline batched by stage (barrier), item0 would deadlock → time out → None. It doesn't.
    gate = asyncio.Event()

    async def s1(x, item, i):
        if i == 0:
            await asyncio.wait_for(gate.wait(), timeout=2)
        return x

    async def s2(x, item, i):
        gate.set()
        return x * 10

    assert await pipeline([0, 1, 2], s1, s2, concurrency=4) == [0, 10, 20]
    print("  pipeline   STREAMING proven — a stage-barrier would deadlock; it didn't ✓")

    # a throwing stage drops just that item to None
    async def boom(x, item, i):
        if i == 1:
            raise ValueError("nope")
        return x

    assert await pipeline([1, 2, 3], boom) == [1, None, 3]
    print("  pipeline   throwing stage → that item None, others fine ✓")

    # parallel: barrier fan-out + concurrency cap + throw→None
    inflight = {"n": 0, "max": 0}

    async def task(v):
        inflight["n"] += 1
        inflight["max"] = max(inflight["max"], inflight["n"])
        await asyncio.sleep(0.01)
        inflight["n"] -= 1
        if v == 5:
            raise RuntimeError("x")
        return v * v

    out = await parallel([(lambda v=v: task(v)) for v in range(6)], concurrency=2)
    assert out == [0, 1, 4, 9, 16, None] and inflight["max"] <= 2, (out, inflight["max"])
    print("  parallel   barrier + cap(≤2) + throw→None ✓  max-inflight", inflight["max"])

    # run_until — loop until predicate, bounded
    box = {"n": 0}

    async def step(i):
        box["n"] += 1
        return box["n"]

    ru = await run_until(step, lambda r: r >= 3)
    assert ru["satisfied"] and ru["iters"] == 3
    print("  run_until  loops until predicate (3 iters) ✓")

    # Memo — content-hash resume: same key → thunk runs ONCE
    memo = Memo()
    calls = {"n": 0}

    async def expensive():
        calls["n"] += 1
        return "result"

    k = content_key({"prompt": "do X"}, 42)
    a = await memo.call(k, expensive)
    b = await memo.call(k, expensive)
    assert a == b == "result" and calls["n"] == 1 and memo.hits == 1
    print("  memo       content-hash resume: 2 calls, thunk ran once ✓")

    # with_schema — validate + retry, then raise if never valid
    tries = {"n": 0}

    async def flaky():
        tries["n"] += 1
        return {"ok": tries["n"] >= 2}

    assert await with_schema(flaky, lambda x: x.get("ok") is True, retries=2) == {"ok": True} and tries["n"] == 2
    try:
        await with_schema(lambda: {"ok": False}, lambda x: x["ok"], retries=1)
        assert False
    except SchemaError:
        pass
    print("  schema     validate + retry; raises when never valid ✓")

    print("WORKFLOW-PARITY PASS — pipeline · parallel · run_until · memo · schema")


if __name__ == "__main__":
    asyncio.run(main())
