---
name: cave-leader
description: The leader loop of the leader-driven runtime — a leader proposes ONE message per step (to one teammate, a SET, or ALL/broadcast), teammates run CONCURRENTLY while the leader runs, the guardrail blocks out-of-turn/invalid messages and re-prompts, and the leader can wait/message-others/END. Three modes raw|llm|file. Use to understand how a real team is driven, the concurrency model, or the closed-world vs open-world rules. Triggers: "the leader", "leader modes", "broadcast", "guardrail", "whose turn", "concurrent teammates", "open rules", "cave-leader".
---

# cave-leader — how a team is actually driven

A cave-team is **always a LEADER + teammates**. The leader is an intelligent, autonomous DOVETAIL:
it receives the task, reasons, and **proposes one message** per step. cave-teams does **not** just
run whatever it says — it **CHECKS** the proposed message against the guardrails and, if invalid,
re-prompts the leader with the error so it self-fixes. Valid → deliver + run.

> This drives the **cave-run-team** runtime and writes **cave-messages** files. Read those alongside.

## What the leader proposes each step — a `Proposal`

```python
Proposal(to="", prompt="", path="", one_liner="", wait=False, end=False, report="")
```

- **`to`** — dispatch to **one** teammate (`to="writer"`), a **SET**, or **ALL** (broadcast):
  `to=["security","perf","tests"]`. Same message goes to every named teammate at once.
- **`path`** — a file for them to use (e.g. a prior teammate's output artifact). Pointer, not payload.
- **`wait=True`** — nothing to send; block until the next in-flight teammate finishes.
- **`end=True` + `report`** — finish the run (any in-flight work is cancelled).

## The concurrency model (this is the part people get wrong)

**Teammates run as CONCURRENT asyncio tasks — they run WHILE the leader runs.** When the leader
dispatches to a set/all, every target starts as its own task. The leader is then **alerted as EACH
one finishes** (not all-at-once): the finish-alert carries `still_running`, and the leader can
`{"wait":true}` for the next finish, **message someone else**, or **END**. The whole run executes in
**one event loop** so async runtimes share it.

- Messaging a teammate that is **still running** is guardrail-blocked (wait for its result first).
- The alert tells the leader **how to CHECK the work** — `message_path`, `history_id`,
  `transcript_path` — and the message PATH to read. **The output is never inlined into the alert;**
  the leader inspects the file/ids. (Force the work to be *checked*, not *fed*.)

## The two tiers of between-agent rules

- **CLOSED-WORLD (enforced).** The topology, compiled to edge-conditions: *is the target a member?
  is it that agent's turn? is the format valid?* Checked mechanically by `check_proposal` — on a
  violation it **blocks and re-prompts** with the exact error, e.g.
  `"It isn't writer's turn — these can run now: ['researcher']. Message one of them."` Order is
  enforced; re-dispatching an agent that already responded is **allowed** (revision loops, follow-ups,
  producer↔critic iteration are the leader's call; `max_steps` bounds the run).
- **OPEN-WORLD (`open_rules={agent:[str]}`, NOT enforced).** Intelligent-reliant rules only the
  leader can judge. cave-teams **surfaces** them in the alert and **assumes they hold** when the
  leader invokes the next teammate — by dispatching, the leader *asserts* the prior step's open rules.

The guardrail is `cave_teams.runner.check_proposal(proposal, team_agents, edges, log, in_flight)` →
returns an error string (re-prompt) or `None` (valid). `max_fixes` bounds the re-prompt retries.

## The three leader modes

```python
from cave_teams import run_team
from cave_teams.runner import llm_leader, file_leader

# 1. raw — the LeaderFn IS your decision function (deterministic tests, coded orchestration):
def my_leader(ctx):            # ctx: task, team_agents, log, in_flight, alert, error
    return Proposal(to="researcher", prompt="find 3 facts", path=ctx["task_path"])
run_team(team, task, my_leader, runtimes, team_dir)

# 2. llm_leader — wrap any runtime (.run(str)->str); it emits ONE JSON object, parsed to a Proposal:
run_team(team, task, llm_leader(minimax_runtime), runtimes, team_dir)
#   → the LLM replies {"to":"writer","prompt":"…","path":"…"} | {"wait":true} | {"end":true,"report":"…"}

# 3. file_leader — Isaac's spec: the leader WRITES its JSON message to a file in leader_outbox
#    using its file-editing tool; cave-teams reads that file, parses, checks, re-prompts.
run_team(team, task, file_leader(minimax_runtime_with_tools), runtimes, team_dir)
#   → leader_runtime MUST have file tools (e.g. MiniMaxRuntime(tools=None) → Bash + NetworkEditTool)
```

`cave_team(...)` (the ephemeral-server runtime) uses **`file_leader`** by default — see
**cave-run-team**.

## The leader's context each step (`ctx`)

`task`, `task_path`, `team_agents`, `outbox` (where a file_leader writes), `log` (every message so
far), `in_flight` (who's still running), `alert` (the last finish-alert), `error` (the last guardrail
rejection, if any). A real leader is prompted with all of this and must reply with exactly one JSON
message.

## See also
`cave-run-team` (the loop that calls the leader) · `cave-messages` (the files it writes) ·
`cave-conditions` (how the topology compiles to the closed-world guardrails). Part of the
**cave-teams** plugin.
