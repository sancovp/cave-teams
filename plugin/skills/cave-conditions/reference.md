# Conditions / the message state machine — reference

## Signature

```python
from cave_teams import (Condition, Edge, responded, after, when_flag, when_message,
                        all_of, any_of, always, register_condition, get_condition,
                        compile_to_edges, run_team, run_team_async, check_proposal, Proposal)

Condition = Callable[[List[TeamMessage]], bool]      # a predicate over the team's message log
Edge(to: str, conditions: List[Condition] = [])      # "may message `to` when ALL conditions hold"
compile_to_edges(topology: Link) -> List[Edge]       # the algebra → the guardrails
run_team(team, task, leader, teammate_runtimes, team_dir,
         open_rules=None, session_id="session", on_event=None,
         max_steps=100, max_fixes=3) -> dict
```

## Condition builders

| builder | meaning |
|---|---|
| `responded(agent)` | True once `agent` has written a RESPONSE message |
| `after(*agents)` | join/barrier — True once EVERY named agent has responded |
| `when_flag(name, value=True)` | True when the latest FLAG message for `name` equals `value` |
| `when_message(pred)` | True if ANY message matches `pred(msg)` — the open, Turing-complete check |
| `all_of(*conds)` / `any_of(*conds)` | combine conditions |
| `always()` | unconditional (the entry edge) |
| `register_condition(name, cond)` / `get_condition(name)` | name conditions so team CONFIGS reference them |

## How it enforces (the guardrail loop)

1. The LEADER (an intelligent, autonomous dovetail) proposes a message (`Proposal(to, prompt, path)`;
   `to` is a name or a LIST — broadcast to some/all) — writing it to the session's `leader_outbox`
   (`file_leader`) or replying JSON (`llm_leader`).
2. `check_proposal` checks it: member of the team? conditions on its edge satisfied by the log?
   not still in flight?
3. Invalid → the leader is re-prompted with the error `{e}` (max `max_fixes` per step) and self-fixes.
4. Valid → delivered to `inbox/<teammate>/`, the teammates run as CONCURRENT tasks (they run while
   the leader runs), and the leader is alerted as EACH finishes with the response PATH + how to
   check the work (history_id / transcript_path) + that step's `open_rules` + `still_running`.
5. The leader sends the next message, `{"wait": true}`s for the next in-flight finish — or ENDS
   with a report (in-flight work is cancelled).

Re-dispatch to an agent that already responded is ALLOWED (revision loops, follow-ups) — conditions
enforce ORDER only; `max_steps` bounds the run.

## Two tiers of between-agent rules

| tier | who checks | how |
|---|---|---|
| CLOSED-WORLD | cave-teams, mechanically | the `Edge.conditions` above — block + re-prompt |
| OPEN-WORLD | the leader's intelligence | `open_rules={agent: ["rule", ...]}` on `run_team` — surfaced in the leader's alert, ASSUMED true when the leader invokes the next teammate |

## Notes

**Not a `cave()` build-op.** Conditions are the message *state machine* (a separate runtime axis),
not a composition Link. `gate`/`choice` do NOT compile to edges (the loop/branch is the LEADER's
decision in a team run — `compile_to_edges` raises a TypeError telling you so); run those
in-process (`await link.execute(...)` / `cave()`), or express the iteration as `open_rules`.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
