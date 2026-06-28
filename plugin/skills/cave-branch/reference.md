# Branch (`choice` / `router`) — reference

## Signature

```python
from cave_teams import choice
choice(routes: List[Tuple[Callable[[dict], bool], Link]],
       default: Optional[Link] = None, name: str = "choice") -> Router
```

## Parameters

| param | meaning |
|---|---|
| `routes` | list of `(guard, link)`; runs the FIRST link whose guard(context) is True |
| `default` | Link to run if no guard matches (else passes the context through) |
| `name` | label |

## Examples

```python
is_code = lambda ctx: ctx.get("kind") == "code"
is_doc  = lambda ctx: ctx.get("kind") == "doc"
routed = choice([(is_code, coder), (is_doc, writer)], default=triage)
res = await routed.execute({"goal": "...", "kind": "code"})
```

## cave() op (drive it from data)

```json
{"op": "choice",
 "routes": [{"if_key": "kind", "equals": "code", "link": <spec>},
            {"if_contains": {"key": "output", "text": "error"}, "link": <spec>}],
 "default": <spec>}
```

## Notes

Guards are plain Python predicates over the context dict — the open, Turing-complete branch. In the `cave()` spec the guards must be DATA: `{"if_key","equals"}` or `{"if_contains":{"key","text"}}`. A guard that raises is treated as False. For runtime message-gating (fire on flags/joins) see **cave-conditions** instead.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
