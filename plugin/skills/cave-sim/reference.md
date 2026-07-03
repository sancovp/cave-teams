# Crafter sim (`crafter_sim`) — reference

## Signature

```python
from pathlib import Path
from cave_teams import crafter_sim, AgentLink
async crafter_sim(population_dirs: List[str],
                  spawn: Callable[[str], Link],
                  judge: Link,
                  generations: int = 3,
                  workdir: str = "/tmp/crafter_sim",
                  k: int = 1,
                  on_generation: Optional[Callable[[int, list, list], None]] = None) -> dict
```

## Parameters

| param | meaning |
|---|---|
| `population_dirs` | seed AIOS directories — the starting population |
| `spawn` | `spawn(dir) -> Link` builds a crafter from an AIOS dir (its `.name` should be the dir’s basename) |
| `judge` | selects winners each generation (often the user’s purchase) |
| `generations` | how many generations to run |
| `k` | how many winners to keep per generation |
| `on_generation` | callback `(gen, results, winners)` for observation |

## Examples

```python
result = await crafter_sim(
    population_dirs=["seed1", "seed2"],
    spawn=lambda d: AgentLink(Path(d).name, "craft the best X", backend="minimax"),
    judge=user_purchase_judge,
    generations=3)
```

## Notes

**Not a single `cave()` build-op** — a composed async simulation engine over **cave-tournament** (compete + select) + **cave-evolve** (breed). Each generation: `spawn` crafters from dirs → they compete → `judge` selects → winners evolve into the next generation. A compiler (a domain → a trained agent) and a research lab (selection discovers what works) in one.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
