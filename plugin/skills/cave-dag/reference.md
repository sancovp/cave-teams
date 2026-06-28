# DAG scheduler (`dag`) — reference

## Signature

```python
from cave_teams import dag
dag(nodes: Union[Dict[str, Link], List[Tuple[str, Link]]],
    deps: Optional[Dict[str, List[str]]] = None, name: str = "dag") -> DagChain
```

## Parameters

| param | meaning |
|---|---|
| `nodes` | named Links: `{"fe": fe, "be": be, "merge": merge}` |
| `deps` | blockedBy map: `{"merge": ["fe", "be"]}` — merge runs after fe AND be |
| `name` | label |

## Examples

```python
flow = dag({"fe": fe, "be": be, "merge": merge}, deps={"merge": ["fe", "be"]})
res = await flow.execute({"goal": "build the page"})
```

## cave() op (drive it from data)

```json
{"op": "dag",
 "nodes": {"fe": <spec>, "be": <spec>, "merge": <spec>},
 "deps": {"merge": ["fe", "be"]}}
```

## Notes

The general partial-order scheduler: each node fires as soon as everything it depends on has finished; independent nodes run concurrently. `seq` (linear deps) and `par` (no deps) are its two limits — reach for `dag` when you have a diamond / fan-in (merge-after-N).

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
