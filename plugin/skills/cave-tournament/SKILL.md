---
name: cave-tournament
description: N agents attempt the same task in parallel and a judge selects the winner (also scatter-gather / map-reduce). Use for 'best of N', contests, judge panels, generate-and-select, picking the strongest output. `tournament()` / `synthesis_gate()`.
---

# Tournament — N agents compete, a judge picks the best

N competitors craft in parallel, then a judge selects (the tree-search pattern) — `tournament(competitors, judge)`. The general scatter→merge form is `synthesis_gate(workers, reducer)` (map-reduce): run workers in parallel, then a reducer sees every output.

## Native API (how you program)

```python
from cave_teams import tournament, synthesis_gate
best = tournament([minimalist, bold, nerdy], judge)
merged = synthesis_gate([clarity, punch, honesty], synthesizer)   # map-reduce
```

The judge/reducer reads the competitors' outputs (`output:<name>` keys). In the crafter sim, the judge is the **user's purchase** — the sound external gate.

## Via cave() (drive it from data)

```json
{"op": "tournament", "competitors": [<spec>, ...], "judge": <spec>}
// or: {"op": "map_reduce", "workers": [<spec>, ...], "reducer": <spec>}
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-tournament skill"}` — the error names this skill.

## See also
`cave-parallel` · `cave-evolve` · `cave-sim`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
