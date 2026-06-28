---
name: cave-branch
description: Run different agents depending on a condition (guarded choice / router). Use for 'if X do this else that', routing, triage, picking a path by the state. `choice()` / `router()`.
---

# Branch — run an agent only if a condition holds

Run the first route whose guard predicate over the context is true, else the default. Guards are plain predicates `Callable[[ctx], bool]` — the open, Turing-complete branch.

## Native API (how you program)

```python
from cave_teams import choice
routed = choice([(is_code, coder), (is_doc, writer)], default=triage)
# guards are predicates over the context dict: is_code = lambda ctx: ctx["kind"] == "code"
```

## Via cave() (drive it from data)

```json
{"op": "choice",
 "routes": [{"if_key": "kind", "equals": "code", "link": <spec>}],
 "default": <spec>}
// data guards: {"if_key","equals"} or {"if_contains":{"key","text"}}
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-branch skill"}` — the error names this skill.

## See also
`cave-conditions` · `cave-dag` · `cave-teams`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
