---
name: cave-sim
description: Run agents that craft, compete, and evolve over generations — the user buys the best, winners reproduce. A compiler (a domain → a trained agent) and a research lab (selection discovers what works) in one engine. `crafter_sim()`.
---

# Sim — the economic crafter simulation

`crafter_sim(population_dirs, spawn, judge, generations)` runs the loop: each generation, `spawn(dir)` builds a crafter Link from an AIOS dir, the crafters compete, the `judge` (often the user's purchase) selects, and the winners evolve into the next generation. The async engine over **cave-tournament** + **cave-evolve**.

## Native API (how you program)

```python
from cave_teams import crafter_sim
result = await crafter_sim(
    population_dirs=["seed1", "seed2"],
    spawn=lambda d: HeavenMiniMaxLink(name=d, system_prompt="craft the best X"),
    judge=user_purchase_judge,
    generations=3)
```

**Not a single `cave()` build-op** — it's a composed simulation engine. Call `crafter_sim()` directly, or assemble the pieces with **cave-tournament** + **cave-evolve** + **cave-world**.

## See also
`cave-tournament` · `cave-evolve` · `cave-world`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
