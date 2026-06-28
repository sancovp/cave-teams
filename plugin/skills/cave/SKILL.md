---
name: cave
description: Drive the whole cave-teams library from one function, as DATA — build/run any team from a spec in any sequence, save a team to your proven library, reuse a proven team anywhere, and discover teams across projects. Use when you want to serialize a team, run a team from JSON/dict, save+reuse a proven team across repos ("golden"), or have a higher system / global app drive cave-teams. NOT how you normally program (use the cave-teams DSL for that). Triggers: "cave()", "metacontrol", "run from a spec", "team as data", "golden team", "reuse a proven team", "scan for .cave", "global cave".
---

# cave — the metacontrol function

**This is NOT how you program with cave-teams.** You program with the native API — the `>>` / `|`
DSL and the pattern functions (see the **cave-teams** skill and each `cave-<pattern>` skill). That
is ergonomic and direct.

`cave()` is the layer **above**: one super-compiled function that can call **everything** in the
native API, in **any sequence**, from a plain-data spec. Reach for it when you want to: serialize a
team as data, run a team from JSON/a dict, save and reuse a proven team across projects, or let a
higher system (or a global app) drive the whole library through one door.

## Run any team from a spec

A spec is a tree of `{"op": ..., ...}` nodes. `cave()` builds it (dispatching `op` recursively over
the native API) and runs it. It **never throws** — it returns a uniform envelope.

```python
import asyncio
from cave_teams import cave, registered_ops

spec = {"op": "seq", "links": [
    {"op": "par", "links": [
        {"op": "agent", "name": "security"},
        {"op": "agent", "name": "perf"}]},
    {"op": "agent", "name": "ship"}]}

result = await cave(spec, context={"goal": "ship the feature"})
# {"status": "success"|..., "context": {...}, "error": None}

await cave(spec, describe_only=True)   # build + describe, don't run (dry run)
registered_ops()                        # every op cave() can drive
```

Each `cave-<pattern>` skill gives that pattern's `op` shape. On a malformed spec you get
`{"status": "construction_error", "error": ..., "hint": "read the cave-<op> skill"}` — the error
names the exact skill to read. Construction errors (you built the spec wrong) are distinct from
`runtime_error` (it ran and broke).

## The proven-team library (build once, reuse forever)

Save a team you trust, then drop it into any project as one building block.

```python
await cave(spec, name="ship_crew", save=True)   # propose → .cave/quarantine/
await cave(goldenize=True, name="ship_crew")     # YOU approve → .cave/golden/  (human-gated)

# reuse the proven team — in the native DSL:
from cave_teams import golden
release = planner >> golden("ship_crew") >> publish
# …or inside any spec:  {"op": "golden", "name": "ship_crew"}

await cave(search="ship")                        # find proven teams (RAG over golden)
```

Goldenizing is the **one un-automated arc**: the agent proposes (save → quarantine), the human
approves (goldenize). A goldenized team becomes a callable op — that's how the metacontrol surface
**grows**.

## Discover teams across projects (for a global cave)

```python
from cave_teams import scan_caves, scan_library
scan_caves(roots=["~/work"])              # every .cave project + its golden/quarantine teams
scan_library(roots=["~/work"], kind="golden")   # individual golden specs of one kind
```

The `roots` you pass **are the boundary** — nothing outside them is touched, heavy dirs
(`node_modules`/`.git`/…) are pruned. A global `.cave` (a separate app) uses `scan_caves` to
enumerate and federate every cave-enabled project.

## Extend it

```python
from cave_teams import register, register_fn
register("my_pattern", lambda s: my_builder(...))   # add a canonical op
register_fn("my_mutator", fn)                        # name a callable for blackboard/world/season specs
```

The native API is the instruction set; `cave()` is the interpreter; `register`/`register_fn` +
`goldenize` extend the instruction set.

## See also
`cave-teams` (the language) · every `cave-<pattern>` skill (each pattern's `op` shape)

Sync, no daemon, never throws. Part of the **cave-teams** plugin.
