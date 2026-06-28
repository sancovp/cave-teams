#!/usr/bin/env python3
"""context_engineering — compose_context / weave_text (native) + the sdna re-export. NO API."""
from cave_teams.context_engineering import (
    compose_context, weave_text, inject_context, CONTEXT_ENGINEERING_SOURCE,
)


def main():
    # compose an agent prompt from named blocks (the inject/assembly layer)
    prompt = compose_context({"role": "You are an NPC blacksmith.", "tools": "forge, trade"})
    assert "## role" in prompt and "blacksmith" in prompt and "## tools" in prompt
    print("  compose   assembled an agent prompt from blocks ✓")

    # weave a slice out of a source text
    src = "L0\nL1\nL2\nL3\nL4"
    assert weave_text(src, 1, 3) == "L1\nL2"
    print("  weave     spliced a line-range out of a source ✓")

    # inject_context is available either way (don't invoke the sdna one — it drives a live transport)
    assert callable(inject_context)
    if CONTEXT_ENGINEERING_SOURCE == "native-only":
        assert isinstance(inject_context({"a": "1"}), str)

    print(f"  source    CONTEXT_ENGINEERING_SOURCE = {CONTEXT_ENGINEERING_SOURCE}  (sdna = real weave/inject wired)")
    print("CONTEXT-ENGINEERING PASS — inject/weave assembly layer in cave_teams")


if __name__ == "__main__":
    main()
