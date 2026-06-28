# Parallel (`par` / `|`) — reference

## Signature

```python
from cave_teams import par
par(*links: Link, name: str = "par") -> ConcurrentChain
# operator form: a | b | c
```

## Parameters

| param | meaning |
|---|---|
| `*links` | Links to run concurrently; each gets a COPY of the incoming context |
| `name` | label for the ConcurrentChain |

## Examples

```python
reviews = clarity | punch | honesty
res = await reviews.execute({"goal": "review this tagline"})
res.context["output:clarity"]   # each branch kept under output:<name>
res.context["_concurrent"]       # list of every branch's full result context
```

## cave() op (drive it from data)

```json
{"op": "par", "links": [<spec>, <spec>, ...]}
```

## Notes

Merge policy: start from the incoming context, fold in each branch's new/changed keys (later branches win on a genuine conflict); every branch's context is also collected under `_concurrent`. First error/blocked status is returned (with the merged context). To reduce the branches with an agent, feed into a reducer — see **cave-tournament** (`synthesis_gate`).

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
