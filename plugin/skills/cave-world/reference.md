# World (`GameWorld`) — reference

## Signature

```python
from cave_teams import GameWorld, world_as_agent
GameWorld.from_spec(spec: dict, agents: Dict[str, Link],
                    mutator: Callable[[dict, str, Any], dict],
                    deity: Optional[Link] = None) -> GameWorld
world_as_agent(world: GameWorld, derive_action: Callable[[dict], Any],
               name="world_agent", inner_key="inner_board") -> Link
```

## Parameters

| param | meaning |
|---|---|
| `spec` | `{rounds, seasons, reset_to, ratchet, name}` — the economy/world compiler input |
| `agents` | the world’s agents (named Links) |
| `mutator` | the board mutator `(board, name, value) -> board` (REQUIRED) |
| `deity` | optional adjudicator Link |
| `world_as_agent` | wrap a whole world so it plays as ONE agent inside a bigger world |

## Examples

```python
w = GameWorld.from_spec({"rounds": 3, "seasons": 2, "reset_to": "board"}, agents, mutator, deity=deity)
res = await w.execute({"board": {}})
inner = world_as_agent(w, derive_action)   # this world is now a player in a bigger world
outer = GameWorld({"w": inner}, mutator)   # worlds nest
```

## cave() op (drive it from data)

```json
{"op": "world",
 "spec": {"rounds": 3, "seasons": 2, "reset_to": "board"},
 "agents": {"a": <spec>}, "mutator": "my_mutator", "deity": <spec>}
```

## Notes

A `GameWorld` composes the arena + gate + season into one object that is itself a `Link` — so worlds nest (`world_as_agent`). `mutator` is a required callable → `register_fn` it for the `cave()` spec. Instantiate, subclass, or `from_spec`.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
