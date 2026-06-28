# Season (bounded epochs) — reference

## Signature

```python
from cave_teams import season, carry_reset_ratchet
season(arena: Link, advance: Optional[Callable[[dict, int], dict]] = None,
       seasons: int = 1, state_key: str = "board", name: str = "season") -> Season
```

## Parameters

| param | meaning |
|---|---|
| `arena` | the Link to run each epoch (often a blackboard or a gate) |
| `advance` | `(state, season_index) -> state` applied BETWEEN epochs (carry / reset / ratchet); None = no carry |
| `seasons` | how many epochs to run |
| `state_key` | the context key carried across epochs |

## Examples

```python
from cave_teams import carry_reset_ratchet
adv = carry_reset_ratchet(reset_to="board", ratchet="best")
s = season(arena, advance=adv, seasons=4)
res = await s.execute({"board": {}})
```

## cave() op (drive it from data)

```json
{"op": "season", "arena": <spec>, "seasons": 4, "advance": "my_advance"}
// advance is optional and a callable -> register_fn it and reference the name
```

## Notes

Runs the arena `seasons` times, applying `advance` between epochs to carry/reset/ratchet the standard — the bar can climb each season. `carry_reset_ratchet(reset_to=..., ratchet=...)` is the built-in advance. `advance` is a Python callable — for `cave()`, `register_fn` it.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
