---
name: cave-gate
description: Loop an agent until a checker approves (a bounded fixpoint that always terminates). Use for 'draft then review until approved', refinement loops, write→critique→revise, retry-until-pass. `gate()` / `loop_refine()`.
---

# Gate — loop an agent until a checker approves

Run the body, then an evaluator; repeat until the evaluator sets `context['approved']` truthy, or `max_cycles` is hit. Two proven laws: **P1 termination** (halts in ≤ max_cycles) and **P2 gate-soundness** (SUCCESS ⟺ the evaluator approved). Wrap a critic agent so its verdict becomes the `approved` flag.

## Native API (how you program)

```python
from cave_teams import gate, loop_refine
draft = gate(writer >> critic, approver, max_cycles=3)   # approver sets context["approved"]
# shorthand for worker/critic refinement:
draft = loop_refine(writer, critic, max_cycles=3)
```

**The evaluator must set `context['approved']`.** A plain agent writes text, not the flag — wrap it so its verdict (e.g. contains 'APPROVE') becomes `context['approved'] = True`.

## Via cave() (drive it from data)

```json
{"op": "gate", "body": <spec>, "evaluator": <spec>, "max_cycles": 3}
// or: {"op": "loop", "worker": <spec>, "critic": <spec>, "max_cycles": 3}
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-gate skill"}` — the error names this skill.

## See also
`cave-sequential` · `cave-conditions` · `cave-teams`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
