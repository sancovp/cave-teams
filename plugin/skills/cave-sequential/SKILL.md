---
name: cave-sequential
description: Run agents one after another (a pipeline); each reads the previous one's output. Use when one step feeds the next, or the user says 'in order', 'then', 'pipeline', 'A then B then C', 'sequential'. The `>>` operator / `seq()`.
---

# Sequential — run agents in order

Run agents in order — each reads the previous one's `output` from the context. The `>>` operator, or `seq(a, b, c)`. Sequential is the limit of `dag` with linear dependencies.

## Native API (how you program)

```python
team = research >> write >> ship
# or, by function:
from cave_teams import seq
team = seq(research, write, ship)
```

## Via cave() (drive it from data)

```json
{"op": "seq", "links": [<spec>, <spec>, ...]}
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-sequential skill"}` — the error names this skill.

## See also
`cave-parallel` · `cave-dag` · `cave-teams`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
