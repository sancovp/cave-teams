---
name: cave-world
description: Compose an arena + gate + season into one GameWorld — a whole simulation/economy that is itself a Link, so worlds nest inside worlds. Use for 'a world of agents', simulations, economies, agents that craft/compete/evolve. `GameWorld`.
---

# World — a whole simulation as one program

`GameWorld` composes the arena, the gate, and the season into one object — and it's a `Link`, so a world can be a player inside a bigger world (`world_as_agent`). Instantiate, subclass, or build from a small spec.

## Native API (how you program)

```python
from cave_teams import GameWorld, world_as_agent
w = GameWorld.from_spec({"rounds": 3, "seasons": 2, "reset_to": "board"}, agents, mutator, deity=deity)
inner = world_as_agent(w, derive_action)   # a whole world plays as ONE agent in a bigger world
```

`mutator` is a required Python callable — `register_fn` it and reference the name in the spec.

## Via cave() (drive it from data)

```json
{"op": "world",
 "spec": {"rounds": 3, "seasons": 2, "reset_to": "board"},
 "agents": {"a": <spec>}, "mutator": "my_mutator", "deity": <spec>}
// mutator referenced by name (register_fn)
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-world skill"}` — the error names this skill.

## See also
`cave-blackboard` · `cave-season` · `cave-sim`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
