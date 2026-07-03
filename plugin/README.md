# cave-teams — Claude Code plugin

**Program agent teams for any coding agent.** The programmable, provider-agnostic version of Claude
Code Teams: wire agents together with a tiny DSL (`>>` and `|`), loop/contest/evolve topologies, and
game-worlds. **CAVE = Coding Agent Virtualization Environment.**

This plugin makes [cave-teams](https://github.com/sancovp/cave-teams) usable from inside Claude Code:
it teaches Claude the API via skills (one per pattern + the metacontrol).

## Install

```
/plugin marketplace add sancovp/cave-teams
/plugin install cave-teams
pip install cave-teams
```

## What's in it

**Skills** (Claude activates these automatically when you talk about agent teams):
- `cave-teams` — the core model + the `>>` / `|` DSL + how to make and run a team (`reference.md` = full API)
- `cave` — the metacontrol: drive ANY pattern from a data spec + the golden (proven-team) library
- one skill per pattern: `cave-sequential` · `cave-parallel` · `cave-branch` · `cave-gate` ·
  `cave-conditions` · `cave-dovetail` · `cave-dag` · `cave-blackboard` · `cave-tournament` ·
  `cave-evolve` · `cave-season` · `cave-world` · `cave-sim` · `cave-metacog`

**CLI:** `cave-teams <spec.json>` — the `cave()` metacontrol function on argv (build / run /
describe / save / goldenize / search any team from a data spec). Installed with `pip install cave-teams`.

## The idea

Everything is the same shape, so everything composes: `agent = team = world`. Two operators wire
anything (`a >> b` in order, `a | b` at once), and the leaves can be any agent — Claude Code, Codex,
MiniMax, a model call, or a function you `lift()` in. Build Claude-Code-Teams-equivalent systems,
and better ones, that you actually control.

MIT.
