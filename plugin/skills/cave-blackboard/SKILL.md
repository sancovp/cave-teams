---
name: cave-blackboard
description: N agents read and write a shared state over rounds, with a mutator that folds each contribution in and an optional adjudicator (stigmergy arena). Use for agents collaborating on a shared board, a market, a workspace they all see. `blackboard()`.
---

# Blackboard — a shared-workspace arena

The arena / stigmergy core: N agents ↔ a shared state ↔ a mutator (`(board, name, value) -> board`) over `rounds`, with an optional adjudicator Link. The gameworld's core building block.

## Native API (how you program)

```python
from cave_teams import blackboard
from cave_teams import register_fn
# the mutator folds each agent's contribution into the shared board:
def keep_latest(board, name, value): return {**board, name: value}
arena = blackboard({"a": a, "b": b}, keep_latest, adjudicator=judge, rounds=3)
```

**The mutator is required** and is a Python callable. For the `cave()` spec, register it by name (`register_fn`) and reference the name — that's the callable axis of extending the metacontrol surface.

## Via cave() (drive it from data)

```json
{"op": "blackboard", "agents": {"a": <spec>, "b": <spec>},
 "mutator": "keep_latest", "rounds": 3}
// the mutator is referenced BY NAME — register it first:
//   cave_teams.register_fn("keep_latest", keep_latest)
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-blackboard skill"}` — the error names this skill.

## See also
`cave-season` · `cave-world` · `cave`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
