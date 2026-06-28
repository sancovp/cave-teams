#!/usr/bin/env python3
"""Phase-1 core smoke: vendored chain_ontology + ConcurrentChain + Dovetail. NO API."""
import asyncio
import os
import tempfile
import time

from cave_teams.chain_ontology import Chain, Link, LinkResult, LinkStatus
from cave_teams.concurrent import ConcurrentChain
from cave_teams.dovetail import DovetailModel, HermesConfigInput


class MockLink(Link):
    def __init__(self, name, delay=0.0, out=None):
        self.name = name
        self.delay = delay
        self._out = out

    async def execute(self, context=None, **kwargs):
        ctx = dict(context) if context else {}
        if self.delay:
            await asyncio.sleep(self.delay)
        ctx[f"output:{self.name}"] = self._out if self._out is not None else f"[{self.name}]"
        ctx["last"] = self.name
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)


async def main():
    # 1. sequential Chain threads context
    r = await Chain("seq", [MockLink("a"), MockLink("b"), MockLink("c")]).execute({"goal": "x"})
    assert r.status == LinkStatus.SUCCESS and r.context["last"] == "c"
    assert r.context["output:a"] == "[a]" and r.context["output:c"] == "[c]"
    print("  Chain          sequential, context threaded ✓")

    # 2. ConcurrentChain runs links in parallel (wall-clock < serial)
    t0 = time.time()
    r = await ConcurrentChain("par", [MockLink("x", 0.1), MockLink("y", 0.1)]).execute({"goal": "x"})
    el = time.time() - t0
    assert r.status == LinkStatus.SUCCESS and "output:x" in r.context and "output:y" in r.context
    assert el < 0.18, el                      # ~0.1s parallel; serial would be ~0.2s
    assert len(r.context["_concurrent"]) == 2
    print(f"  ConcurrentChain parallel, {el*1000:.0f}ms for 2×100ms (serial≈200ms) ✓")

    # 3. Dovetail: dot-extract + validate + >10k pointer
    d = DovetailModel(name="d", expected_outputs=["result.summary"],
                      input_map={"goal": HermesConfigInput(source_key="result.summary")})
    assert d.prepare_next_inputs({"result": {"summary": "do the thing"}}) == {"goal": "do the thing"}
    try:
        d.prepare_next_inputs({"result": {}})
        assert False, "missing output should raise"
    except ValueError:
        pass
    big = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    big.write("Z" * 20000)
    big.close()
    enr = DovetailModel(name="d2", file_inputs={"doc": big.name})._load_file_inputs({})
    assert enr["doc"].startswith("You must read"), enr["doc"]
    os.unlink(big.name)
    print("  Dovetail       dot-extract · validate · >10k pointer ✓")

    # 4. homoiconic describe (a Chain is a Link → nests)
    desc = Chain("top", [MockLink("a"), Chain("sub", [MockLink("b"), MockLink("c")])]).describe()
    assert 'Chain "top"' in desc and 'Chain "sub"' in desc
    print("  describe       homoiconic nested tree ✓")

    print("CHAIN-ONTOLOGY PASS — vendored Link/Chain/EvalChain + ConcurrentChain + Dovetail")


if __name__ == "__main__":
    asyncio.run(main())
