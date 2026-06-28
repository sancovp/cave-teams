---
name: cave-teams
description: Build and run programmable agent teams with cave-teams — the provider-agnostic version of Claude Code Teams. Use when the user wants to wire multiple agents together, run agents in sequence or parallel, build a multi-agent pipeline/workflow, make a "team" of coding agents (Claude Code, Codex, MiniMax, or any), loop an agent until a check passes, run a contest between agents, or compose agents with the >> / | DSL. Triggers: "agent team", "multi-agent", "orchestrate agents", "wire these agents", "run agents in parallel", "cave-teams", "agent pipeline", "agent workflow".
---

# cave-teams — program agent teams for any coding agent

cave-teams lets you wire AI agents together with a tiny algebra and run them. It is the
**programmable, provider-agnostic** version of Claude Code Teams: the leaves can be any agent
(Claude Code, Codex, MiniMax, a model call, a shell command, a Python function), and you control
the *flow* with code. **CAVE = Coding Agent Virtualization Environment.**

## The one idea

**Everything is the same shape — a `Link`.** An agent is a Link, a team is a Link, a whole world
is a Link. A composition of Links *is* a Link, so teams nest inside teams forever. That is why two
operators are enough to wire anything: `agent = team = world`.

```
pip install cave-teams        # one tiny dependency (universal-chain-ontology)
```

## The two operators (the DSL)

Importing `cave_teams` installs `>>` and `|` on every agent:

```python
import cave_teams
from cave_teams import AgentLink

research = AgentLink("research", "Find 3 key facts about the topic.")
writer   = AgentLink("writer",   "Turn the facts into one punchy paragraph.")

team = research >> writer          # >>  run in order (sequential)
flow = a | b | c                   # |   run at the same time (parallel)

# combine freely — read it left to right:
pipeline = research >> (security | perf | tests) >> ship
```

- `a >> b` — run `a`, then `b`. `b` reads `a`'s output from the context.
- `a | b` — run `a` and `b` concurrently on the same input; their outputs merge.

## Make an agent (the leaf)

A leaf reads its input from the context and writes its reply back. Pick the backend:

```python
from cave_teams import AgentLink            # a model agent (claude-p or minimax backend)
a = AgentLink("name", "system prompt", backend="claude-p", model="claude-sonnet-4-6")
b = AgentLink("name", "system prompt", backend="minimax",  model="MiniMax-M2.7-highspeed")

from cave_teams import HeavenMiniMaxLink     # a real coding agent (Bash + file-edit tools by default)
c = HeavenMiniMaxLink("coder", "Do the task with your tools.")

from cave_teams import lift                  # wrap ANY runnable (a function/callable/agent) into a Link
d = lift(my_existing_agent)                  # provider-agnostic: bring what you already use
```

## Run it

```python
result = await team.execute({"goal": "the topic or task"})
print(result.status)                  # LinkStatus.SUCCESS / ERROR
print(result.context["output"])       # the final reply
print(result.context["output:writer"])# each agent's reply is also keyed by name
```

The context is a dict threaded through the team. Each Link reads `output` (or `goal`/`input` at the
start) and writes `output` + `output:<name>`.

## Compose beyond order/parallel

```python
from cave_teams import gate, tournament, team, choice, dovetail

draft  = gate(writer >> critic)            # loop until the critic approves (always terminates)
best   = tournament(candidates, judge)     # N agents compete, a judge picks the winner
crew   = team(research >> writer)          # name a composition so it nests as one unit
routed = choice([(is_code, coder), (is_doc, writer)], default=triage)   # branch on a condition
piped  = a >> dovetail(D) >> b             # typed hand-off of named data between agents
```

For the gate, the evaluator must set `context["approved"]` (wrap a critic agent so its verdict
becomes that flag). Each pattern has its own skill — **cave-sequential**, **cave-parallel**,
**cave-branch**, **cave-gate**, **cave-conditions** (the message state machine), **cave-dovetail**,
**cave-dag**, **cave-blackboard**, **cave-tournament**, **cave-evolve**, **cave-season**,
**cave-world**, **cave-sim**, **cave-metacog** — and the **cave** skill drives any of them from
data (and is the proven-team / golden library). Full API: `reference.md` in this skill folder.

## What this replaces

| You used to… | With cave-teams |
|---|---|
| write callbacks/queues to wire agents | `a >> b` / `a \| b` |
| hand-roll a retry/approval loop | `gate(worker >> critic)` |
| be stuck with Claude Code Teams' fixed flow | program the flow yourself, for any agent |
| be locked to one vendor | swap the model/agent, keep the wiring |
