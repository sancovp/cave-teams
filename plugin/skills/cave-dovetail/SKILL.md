---
name: cave-dovetail
description: Hand off specific named data from one agent to the next, typed (load files, validate expected outputs, map outputs→inputs). Use when step B needs particular named inputs produced by step A, not just the raw text. `dovetail()`.
---

# Dovetail — typed hand-off of named data between agents

The typed joint between two steps: `a >> dovetail(D) >> b` applies a `DovetailModel` between them — declares the expected outputs of the previous step, loads files into the context, and maps them to the next step's named inputs. A missing expected output surfaces as a BLOCKED/ERROR Link.

## Native API (how you program)

```python
from cave_teams import dovetail, DovetailModel
D = DovetailModel(expected_outputs=["spec"], file_inputs={"plan": "PLAN.md"})
piped = a >> dovetail(D) >> b
```

## Via cave() (drive it from data)

```json
{"op": "dovetail", "a": <spec>, "b": <spec>,
 "model": {"expected_outputs": ["spec"], "file_inputs": {"plan": "PLAN.md"}}}
```

If the spec is malformed, `cave()` returns `{"status": "construction_error", "hint": "read the cave-dovetail skill"}` — the error names this skill.

## See also
`cave-sequential` · `cave-dag` · `cave-teams`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
