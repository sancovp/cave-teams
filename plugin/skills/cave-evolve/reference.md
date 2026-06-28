# Evolve (genetic reproduction) — reference

## Signature

```python
from cave_teams import evolve, evolve_dir, select_winners
evolve(winner_dirs: Sequence[str|Path], out_dir: str|Path,
       prefix: str = "gen", wipe: Optional[Sequence[str]] = None) -> List[str]
evolve_dir(winner_dir, child_dir, wipe=None) -> str
```

## Parameters

| param | meaning |
|---|---|
| `winner_dirs` | the winners’ agent directories (their whole AIOS, incl. emergent structure) |
| `out_dir` | where the next generation is written (`out_dir/{prefix}_{i}`) |
| `wipe` | session-memory paths to remove in each child (so children inherit structure, not history) |
| `returns` | the list of child directories — the next generation |

## Examples

```python
children = evolve(winner_dirs, out_dir="gen2")   # -> ["gen2/gen_0", "gen2/gen_1", ...]
# children inherit the winners’ dir/AIOS but start memory-free
```

## Notes

**Not a `cave()` build-op** — `evolve` is a genetic *filesystem* operation (it copies agent directories and returns child dir paths, not a Link). Call it directly. It is the reproduction step of the loop: **cave-tournament** selects winners → `evolve` breeds the next generation → repeat (see **cave-sim**).

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
