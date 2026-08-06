---
name: cave-teams-volume
description: The front door to cave-teams — the whole library as ONE navigable curriculum. Start here to learn cave-teams the right way: the one idea (everything is a Link), the TWO runtimes (in-process DSL vs leader-driven file spine), then the topologies, metacontrol, and worlds, in dependency order. Use when you want to learn/teach cave-teams, decide which pattern to reach for, or systematically cover every topology. Triggers: "learn cave-teams", "cave-teams curriculum", "which topology", "teach cave teams", "cave-teams-volume", "the course".
---

# cave-teams — the volume (start here)

This is the **rooted course** over the whole cave-teams library. cave-teams' skills used to be a
**flat forest** (16 siblings that all load at once and never say what to read first). This volume
roots them into ONE dependency-ordered tree: you **load this root and walk** to the exact leaf you
need — nothing else pollutes context. (This is the SkillTree pattern: `Tree = Root × Forest`; descend
by using the **Read tool** on a child — see the `## Descend` block the builder appends below.)

## The one idea

**Everything is the same shape — a `Link`.** An agent is a Link, a team is a Link, a whole world is a
Link; a composition of Links *is* a Link, so teams nest forever. `agent = team = world`.

## THE fork everything hangs off — two runtimes

cave-teams has **two ways to actually run a team.** Know which one you mean:

| | **in-process plane** (the DSL) | **leader-driven plane** (the file spine) |
|---|---|---|
| how it runs | `await team.execute(ctx)` **threads a Python dict** through the links | a **leader** routes **message FILES** between agents; a guardrail gates turn-order |
| what a hand-off is | a string in `ctx["output"]`, in memory | a JSON file in `messages/`; dispatch is a **pointer** to a file |
| concurrency | `\|` runs branches concurrently, outputs merge | teammates run as concurrent tasks **while the leader runs**; leader reaped per-finish |
| you reach for it when | wiring a pipeline/contest/loop ergonomically in code | running a **real** autonomous team that reasons about who goes next |
| the skills | `cave-teams` + every `cave-<pattern>` (branch 0.2) | `cave-run-team` · `cave-leader` · `cave-messages` (branch 0.3) |

Most of the library teaches the in-process DSL. The **leader-driven plane is the real execution
model** (rule 01) and was under-taught — branch 0.3 (`cave-leader-spine`) fixes that. `cave()`
(0.4) can drive **either** plane from a data spec (its `team_run` op runs the leader-driven one).

## The course — walk it in this order

```mermaid
flowchart TB
  V[0 cave-teams-volume — you are here] --> ONE[0.1 cave-teams · the one idea: Link, agent=team=world]
  ONE --> IP[0.2 in-process plane · execute threads a dict]
  ONE --> LS[0.3 leader-driven spine · messages are files]
  IP --> IPk["cave-sequential · cave-parallel · cave-branch · cave-conditions<br/>cave-gate · cave-dag · cave-dovetail · cave-tournament"]
  LS --> LSk["cave-run-team · cave-leader · cave-messages"]
  IP --> C[0.4 cave · metacontrol: run any team from DATA]
  LS --> C
  C --> W[0.5 worlds · leader-driven server teams]
  W --> Wk["cave-blackboard · cave-metacog · cave-season<br/>cave-sim · cave-evolve · cave-world"]
  classDef new fill:#1b4,color:#fff; class LS,LSk new
```

- **0.1 `cave-teams`** — the one idea + the `>>` / `|` operators + how to make a leaf agent.
- **0.2 in-process plane** — the topologies you compose with the DSL: sequential, parallel, branch,
  conditions, gate (loop-until-approved), dag, dovetail (typed hand-off), tournament.
- **0.3 leader-driven spine** *(new — the real runtime)* — `cave-run-team` (run it), `cave-leader`
  (who drives it + the guardrail + concurrency + broadcast), `cave-messages` (the file substrate).
- **0.4 `cave`** — the metacontrol function: build/run **any** team from a plain-data spec, in any
  sequence; the `team_run` op runs the leader-driven plane; the golden library; scan across projects.
- **0.5 worlds** — leader-driven server teams built on the spine: blackboard (shared board),
  metacog, season, sim, evolve, world (gameworld).

## Decision tree — what do I reach for?

- *Wire a few agents in code, ergonomically* → **0.1 cave-teams** (`>>` / `|`), then the specific
  **0.2** pattern (in order / parallel / branch / loop / contest / typed hand-off).
- *Run a real autonomous team that decides who goes next, over files* → **0.3** (`cave-run-team`).
- *Store/serialize/reuse a proven team, or drive the library from a higher system as DATA* → **0.4
  cave** (+ goldenize to grow the library).
- *Agents collaborating on shared state over rounds, a market, a game* → **0.5 worlds**.

## Rebuilding this volume

This tree is generated from `curriculum/cave-teams.manifest.json` by
`skilltree build curriculum/cave-teams.manifest.json curriculum/tree` (run from the repo root;
`pip install agent-skilltree`). Each leaf body is carried from that skill's own dir under
plugin/skills (the manifest's `skill_src`), so edit a skill there and rebuild to refresh the course.
The generated
`curriculum/tree/` is a build artifact (breadcrumbs carry absolute paths) — the manifest + the
`plugin/skills/` sources are the committed source of truth.

## See also
Every node below (walk the tree). The flat capability skills live in `plugin/skills/`; this volume is
the *learning* surface over them. Part of the **cave-teams** plugin.
