# Conditions / the message state machine (`Harness`) — reference

## Signature

```python
from cave_teams import Harness, when_flag, when_not_flag, after, when, all_of, any_of
Harness(team_dir: str, on_event: Optional[Callable] = None, concurrent: bool = True)
h.add_condition(agent: str, cond)   # cond: Callable[[Harness, agent], bool]
h.set_flag(name); h.get_flag(name)
```

## Parameters

| param | meaning |
|---|---|
| `team_dir` | working dir for the team (messages/state/transcripts live here) |
| `concurrent` | True = eligible agents fire on their own threads; False = deterministic single-thread (tests) |
| `when_flag(name, value=True)` | fire only when flag == value |
| `after(*agents)` | join/barrier — fire only after each named agent has completed (auto-flag `done:<agent>`) |
| `when(pred)` | fire on any predicate `(harness, agent) -> bool` |
| `all_of/any_of(*conds)` | combine conditions |

## Examples

```python
h = Harness("/tmp/my-team", concurrent=False)
h.add_agent("frontend", fe); h.add_agent("backend", be); h.add_agent("merge", mg)
h.add_condition("merge", after("frontend", "backend"))   # wait for BOTH
h.add_condition("publisher", when_flag("approved"))      # only after approval
h.send_message("frontend", "...")   # control IN; events stream OUT via the EventBus
```

## Notes

**Not a `cave()` build-op.** The `Harness` is the message *runtime*, not a composition Link: an agent FIRES when it (a) has a pending message AND (b) passes its conditions over flags; a flag flip (or an agent finishing) re-evaluates who is eligible and fires them. This is the actor core that makes flow *programmable* (vs Claude Code Teams’ fixed markdown order). Every boundary streams through the EventBus (events OUT); `send_message` is control IN.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
