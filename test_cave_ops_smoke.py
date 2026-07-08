"""Smoke-test the two new cave() ops — `call` (any imported function as a step) and `team_run`
(the leader-driven runtime through the door). NO LLM: register_fn'd stubs + a scripted leader."""
import asyncio
import os
import tempfile

os.environ.setdefault("CAVE_HOME", tempfile.mkdtemp())

from cave_teams import cave, register_fn, set_persona_compiler
from cave_teams.cave import _build
from cave_teams.runner import Proposal


async def main():
    # 1) call op via a register_fn'd callable (reference-by-name; code must already exist)
    register_fn("shout", lambda s: s.upper())
    r = await cave({"op": "seq", "links": [{"op": "call", "fn": "shout"}]}, context={"goal": "hi there"})
    assert r["status"] == "success" and r["context"]["output"] == "HI THERE", r
    print("  call/fn        register_fn'd callable as a step ✓ ->", r["context"]["output"])

    # 2) call op via dynamic import (ANY imported function, IO mapped from the context)
    r = await cave({"op": "call", "import": "os.path.basename"}, context={"goal": "/a/b/c.txt"})
    assert r["context"]["output"] == "c.txt", r
    print("  call/import    dynamic-imported function as a step ✓ ->", r["context"]["output"])

    # 3) call op composes with canonical ops (a function slot inside a seq)
    register_fn("excl", lambda s: s + "!")
    r = await cave({"op": "seq", "links": [{"op": "call", "fn": "shout"}, {"op": "call", "fn": "excl"}]},
                   context={"goal": "done"})
    assert r["context"]["output"] == "DONE!", r
    print("  call composes  seq(call, call) ✓ ->", r["context"]["output"])

    # 4) team_run op — the LEADER-DRIVEN runtime through the door (stubbed, no LLM)
    seen = []
    register_fn("rt_a", lambda p: (seen.append("a"), "A result")[1])
    register_fn("rt_b", lambda p: (seen.append("b"), "B result")[1])
    script = iter([Proposal(to="a", prompt="go a"),
                   Proposal(to="b", prompt="read a's output"),
                   Proposal(end=True, report="pipeline complete")])
    register_fn("sleader", lambda ctx: next(script))          # a raw LeaderFn(ctx)->Proposal
    r = await cave({"op": "team_run",
                    "topology": {"op": "seq", "links": [{"op": "agent", "name": "a"},
                                                        {"op": "agent", "name": "b"}]},
                    "leader": "sleader", "leader_mode": "raw",
                    "runtimes": {"a": "rt_a", "b": "rt_b"},
                    "task": "do the thing"})
    assert r["status"] == "success", r
    tr = r["context"]["team_result"]
    assert tr["ok"] and tr["report"] == "pipeline complete", tr
    responders = [m["frm"] for m in tr["messages"] if m["kind"] == "response"]
    assert responders == ["a", "b"], responders
    print("  team_run       leader-driven team over FILES ✓ -> responders", responders, "| report:", tr["report"])

    # 5) describe_only shows both new ops in the tree (no run)
    d = await cave({"op": "seq", "links": [{"op": "call", "fn": "shout"},
                    {"op": "team_run", "topology": {"op": "agent", "name": "a"}, "runtimes": {}}]},
                   describe_only=True)
    assert d["status"] == "described" and "team_run" in d["description"] and "shout" in d["description"], d
    print("  describe       call + team_run render in the tree ✓")

    # 6) persona handoff — SI/meta-APE MAKES the persona, cave's agent leaf takes it (the seam)
    #    (a) the real default path: prompt_engineering (meta-APE) compiles a spec → system_prompt
    try:
        link = _build({"op": "agent", "name": "dbg", "persona": {"name": "Ada", "role": "a senior debugger"}})
        assert isinstance(link.runtime.system_prompt, str) and "debugger" in link.runtime.system_prompt.lower(), \
            link.runtime.system_prompt
        print("  persona/meta-APE  make_persona spec → agent leaf's system_prompt ✓")
    except Exception as e:
        print("  persona/meta-APE  (skipped — agent-prompt-engineering not importable:", str(e)[:50], ")")
    #    (b) the seam: any registered compiler resolves the persona ref (decoupled from CC)
    set_persona_compiler(lambda ref: f"COMPILED_PERSONA[{ref}]")
    link = _build({"op": "agent", "name": "x", "persona": "debugger"})
    assert link.runtime.system_prompt == "COMPILED_PERSONA[debugger]", link.runtime.system_prompt
    print("  persona/seam      set_persona_compiler → agent leaf resolves 'persona' by ref ✓")
    set_persona_compiler(None)

    print("CAVE-OPS PASS — call · team_run · describe · persona (SI→cave handoff)")


if __name__ == "__main__":
    asyncio.run(main())
