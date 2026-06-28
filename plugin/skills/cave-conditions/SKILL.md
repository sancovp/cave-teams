---
name: cave-conditions
description: Program WHEN each agent fires — the message state machine. Use to gate agents on runtime state: after these two finish, only if a flag/budget holds, only once a check passed — any rule you can write. THIS is what makes cave-teams programmable where Claude Code Teams' flow is fixed.
---

# Conditions — program WHEN each agent runs (the message state machine)

The `Harness` is an actor core: an agent FIRES when it (a) has a pending message AND (b) passes its conditions. Conditions are predicates over runtime FLAGS; a flag flip — or another agent finishing (auto-sets `done:<agent>`) — re-evaluates who is eligible and fires them. Conditions: `when_flag`, `when_not_flag`, `after` (join/barrier), `when` (any predicate), `all_of`, `any_of`.

## Native API (how you program)

```python
from cave_teams import Harness, when_flag, after, when
h = Harness(team_dir)
h.add_condition("publisher", when_flag("approved"))        # only after approval
h.add_condition("merge", after("frontend", "backend"))      # wait for BOTH (join)
h.add_condition("worker", when(lambda hh, a: hh.get_flag("budget") > 0))  # any rule
h.set_flag("approved")                                       # flip state → re-evaluate
```

**Not a `cave()` build-op** — the Harness is the message *runtime* (it gates delivery between persistent agents), not a composition Link. Use it directly. A pipeline/join/branch is just conditions + flags + message wiring.

## See also
`cave-branch` · `cave-gate` · `cave-teams`

Part of the **cave-teams** plugin — the language + full DSL is the **cave-teams** skill; drive any pattern from data with the **cave** skill.
