---
name: cave-metacog
description: A self-improving agent stack that gets better as it works: an executor does the work, an observer extracts patterns, a static meta-observer anchors, and a skill-editor persists the learnings. Use for teams that should compound their own capability over cycles. `metacog_shell()`.
---

# Metacog — a self-improving observer stack

A separate meta-pattern: `metacog_shell(executor, observer, meta, skill_editor, cycles)`. The executor works; the observer extracts patterns; `meta` is the static fixed-point anchor; the skill_editor writes learnings back as skills. Three self-expanding roles around one static anchor — it compounds over `cycles`.

## Native API (how you program)

```python
from cave_teams import metacog_shell
shell = metacog_shell(executor, observer, meta, skill_editor=editor, cycles=3)
result = await shell.execute({"goal": "..."})
```

`metacog_shell()` returns a `MetacogShell` (a Link), so it composes — but build it with the constructor (it wires four roles). Register it as a `cave()` op only if you want to drive it from data.

## See also
`cave-conditions` · `cave-teams` · `cave`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
