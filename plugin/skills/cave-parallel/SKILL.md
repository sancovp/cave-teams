---
name: cave-parallel
description: Run agents at the same time on the same input (fan-out / scatter). Use for 'in parallel', 'at once', 'concurrently', 'fan out', multiple independent reviewers or checks. The `|` operator / `par()`.
---

# Parallel — run agents at once

Run agents concurrently on the same input; each gets a copy of the context and their outputs merge back (each kept under `output:<name>`). The `|` operator, or `par(a, b, c)`. To merge the results with a reducer, see **cave-tournament** (map_reduce).

## Native API (how you program)

```python
reviews = clarity | punch | honesty
# or, by function:
from cave_teams import par
reviews = par(clarity, punch, honesty)
```

## Via cave() (drive it from data)

```json
{"op": "par", "links": [<spec>, <spec>, ...]}
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-parallel skill"}` — the error names this skill.

## See also
`cave-sequential` · `cave-tournament` · `cave-teams`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
