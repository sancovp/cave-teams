# cave-teams

**Connect AI agents like code.** Wire your whole team of AI agents with one line instead of hundreds
of lines of glue — add one, swap one, or reuse a whole team just by changing a word.

cave-teams is the **programmable, provider-agnostic** version of Claude Code Teams. The agents
underneath can be anything (Claude Code, Codex, MiniMax, a model call, a shell command, a Python
function); you control the *flow* with code. **CAVE = Coding Agent Virtualization Environment.**

```bash
pip install cave-teams        # zero-dependency core
```

## The one idea

Everything is the same shape — a building block. An agent is one, a team is one, a whole world is
one. A composition of building blocks *is* a building block, so teams nest inside teams forever
(`agent = team = world`). That is why two operators wire anything:

```python
import cave_teams
from cave_teams import AgentLink

research = AgentLink("research", "Find 3 key facts.")
writer   = AgentLink("writer",   "Turn the facts into a paragraph.")

team = research >> writer                      # >>  run in order
flow = research >> (security | perf | tests) >> ship   # |  run at the same time

result = await flow.execute({"goal": "ship the feature"})
```

## What it does

- **Program any control flow** — agents fire on conditions you write (`when_flag`, `after`, any
  predicate). The message state machine, not a markdown to-do list.
- **Any agents** — `AgentLink` (Claude Code / MiniMax), `HeavenMiniMaxLink` (a real coding agent
  with bash + file-edit), or `lift()` any function / callable.
- **Every topology** — sequential, parallel, branch, loop-until-approved, join (DAG), typed
  hand-off, shared-workspace arena, tournament, evolve, season — and they nest.
- **Provable wiring** — termination, gate-soundness, and distribution are mechanically tested.
- **A whole world of agents** — `GameWorld`, an economic crafter sim, agents that compete and evolve.
- **Build once, reuse forever** — save a proven team to your golden library and drop it into any
  project as one building block.

## Two layers

- **The native API** is how you program — the `>>` / `|` DSL and the pattern functions.
- **`cave()`** is the metacontrol function on top: it drives the whole API from a data spec, in any
  sequence — serialize a team, run it from JSON, save/reuse a proven team, federate caves.

## Claude Code plugin

This repo is also a Claude Code plugin (`plugin/`). It ships a skill per pattern — the language
(`cave-teams`), the metacontrol (`cave`), and one each for sequential / parallel / branch / gate /
conditions / dovetail / dag / blackboard / tournament / evolve / season / world / sim / metacog.
`.claude/skills`, `.codex/skills`, and `.agent/skills` symlink to the same `plugin/skills`, so any
coding agent that clones the repo picks them up.

MIT.
