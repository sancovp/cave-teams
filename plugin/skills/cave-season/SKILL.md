---
name: cave-season
description: Run an arena over a fixed number of epochs (seasons) that carry, reset, or ratchet a standard between them. Use for tournaments/worlds that run several rounds where the bar climbs each season. `season()`.
---

# Season — run an arena over bounded epochs

The bounded epoch boundary: `season(arena, advance, seasons=N)` runs the arena `N` times, applying `advance(state, season_index) -> state` between epochs (carry / reset / ratchet). The World-of-Skillcraft season — the standard climbs.

## Native API (how you program)

```python
from cave_teams import season, carry_reset_ratchet
s = season(arena, advance=carry_reset_ratchet(reset_to="board", ratchet="best"), seasons=4)
```

`advance` is an optional Python callable — for the `cave()` spec, `register_fn` it and reference the name.

## Via cave() (drive it from data)

```json
{"op": "season", "arena": <spec>, "seasons": 4, "advance": "my_advance"}
// advance (optional) is a callable referenced by name (register_fn); omit for no carry
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-season skill"}` — the error names this skill.

## See also
`cave-blackboard` · `cave-world` · `cave`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
