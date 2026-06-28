# Sequential (`seq` / `>>`) — reference

## Signature

```python
from cave_teams import seq
seq(*links: Link, name: str = "seq") -> Chain
# operator form: a >> b >> c   (installed on every Link by importing cave_teams)
```

## Parameters

| param | meaning |
|---|---|
| `*links` | the Links to run in order; each reads the previous one's `output` from the context |
| `name` | label for the resulting Chain |

## Examples

```python
team = research >> write >> ship
team = seq(research, write, ship, name="pipeline")
result = await team.execute({"goal": "..."})
print(result.context["output"])          # final reply
print(result.context["output:write"])    # each step also keyed by name
```

## cave() op (drive it from data)

```json
{"op": "seq", "links": [<spec>, <spec>, ...]}
```

## Notes

`>>` flattens plain Chains, so `(a >> (b >> c)).links == ((a >> b) >> c).links == [a,b,c]` — associativity is structural. A Chain stops on the first non-SUCCESS link. `seq` is the limit of `dag` with linear dependencies.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
