# Blackboard / arena (`blackboard`) — reference

## Signature

```python
from cave_teams import blackboard, register_fn
blackboard(agents: Dict[str, Link],
           mutator: Callable[[dict, str, Any], dict],
           adjudicator: Optional[Link] = None,
           rounds: int = 1, state_key: str = "board") -> Blackboard
```

## Parameters

| param | meaning |
|---|---|
| `agents` | named agents that read+write the shared board |
| `mutator` | `(board, agent_name, value) -> board` — folds each contribution into the shared state (REQUIRED) |
| `adjudicator` | optional Link that judges/closes each round |
| `rounds` | how many rounds the agents iterate over the board |
| `state_key` | the context key holding the board (default `"board"`) |

## Examples

```python
def keep_latest(board, name, value): return {**board, name: value}
arena = blackboard({"a": a, "b": b}, keep_latest, adjudicator=judge, rounds=3)
res = await arena.execute({"board": {}})

# data-driven: register the mutator by name first
register_fn("keep_latest", keep_latest)
```

## cave() op (drive it from data)

```json
{"op": "blackboard", "agents": {"a": <spec>, "b": <spec>},
 "mutator": "keep_latest", "rounds": 3, "adjudicator": <spec>}
```

## Notes

The stigmergy core: N agents ↔ a shared state ↔ a mutator, over `rounds`. **The mutator is required and is a Python callable** — for the `cave()` spec, `register_fn(name, fn)` it and reference the name (missing mutator → construction_error). The gameworld’s building block (see **cave-season**, **cave-world**).

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
