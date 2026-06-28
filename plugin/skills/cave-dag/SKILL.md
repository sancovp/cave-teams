---
name: cave-dag
description: Run agents on a dependency graph — each fires when its inputs are ready (the general scheduler; sequential and parallel are its limits). Use for 'merge after frontend AND backend', diamond/fan-in dependencies, partial orders. `dag()`.
---

# DAG — run agents when their inputs are ready

A `blockedBy` DAG: give the nodes and the dependencies; each node runs as soon as everything it depends on has finished. `seq` (linear deps) and `par` (no deps) are its two limits.

## Native API (how you program)

```python
from cave_teams import dag
flow = dag({"fe": fe, "be": be, "merge": merge},
           deps={"merge": ["fe", "be"]})   # merge waits for fe AND be
```

## Via cave() (drive it from data)

```json
{"op": "dag",
 "nodes": {"fe": <spec>, "be": <spec>, "merge": <spec>},
 "deps": {"merge": ["fe", "be"]}}
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-dag skill"}` — the error names this skill.

## See also
`cave-sequential` · `cave-parallel` · `cave-teams`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
