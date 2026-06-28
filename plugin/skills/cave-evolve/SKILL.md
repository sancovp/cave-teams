---
name: cave-evolve
description: Reproduce a generation: copy each winner's whole agent directory into the next generation and wipe its session memory (children inherit structure, not history). Use for evolving agents/teams across generations. `evolve()`.
---

# Evolve — breed a next generation from the winners

The genetic operator over agent directories: `evolve(winner_dirs, out_dir)` copies each winner's whole AIOS dir into `out_dir/{prefix}_{i}` and removes its knowledge of previous sessions — the next generation, born advanced (the dir) but memory-free. Returns the child dirs.

## Native API (how you program)

```python
from cave_teams import evolve, select_winners
children = evolve(winner_dirs, out_dir="gen2")   # -> list of child dirs
```

**Not a `cave()` build-op** — `evolve` is a genetic *filesystem* operation (it returns child directories, not a Link). Call it directly. It pairs with **cave-tournament** (select winners) and **cave-sim** (run it over generations).

## See also
`cave-tournament` · `cave-sim` · `cave-world`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
