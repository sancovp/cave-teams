# Metacog shell (`metacog_shell`) — reference

## Signature

```python
from cave_teams import metacog_shell
metacog_shell(executor: Link, observer: Link, meta: Link,
              skill_editor: Optional[Link] = None, cycles: int = 1,
              skills_key: str = "skills", name: str = "metacog") -> MetacogShell
```

## Parameters

| param | meaning |
|---|---|
| `executor` | does the work each cycle |
| `observer` | extracts patterns from the executor’s run |
| `meta` | the STATIC fixed-point anchor (the part that does not self-expand) |
| `skill_editor` | optional — persists the learnings as skill edits |
| `cycles` | how many improvement cycles to run |
| `skills_key` | the context key holding the accumulated skills |

## Examples

```python
shell = metacog_shell(executor, observer, meta, skill_editor=editor, cycles=3)
res = await shell.execute({"goal": "..."})
res.context["skills"]   # the accumulated, self-edited skills
```

## Notes

A separate meta-pattern: three self-expanding roles (executor / observer / skill_editor) around one static anchor (`meta`) — it compounds its own capability over `cycles`. `metacog_shell()` returns a `MetacogShell` (a Link), so it composes; build it with the constructor (it wires four roles). Register it as a `cave()` op only if you want to drive it from data.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
