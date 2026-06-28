# cave — the metacontrol function — reference

`cave()` drives the whole native API from a data spec. It is **not** how you program (use the native
DSL for that) — it is the universal driver/interpreter over the library. Sync, never throws.

## Signature

```python
from cave_teams import cave
async cave(spec: Any = None, *,
           name: Optional[str] = None,
           context: Optional[dict] = None,
           execute: bool = True,        # build + run, return the run envelope
           save: bool = False,          # write the spec to .cave/quarantine/
           goldenize: bool = False,     # promote quarantine -> golden (HUMAN approval)
           describe_only: bool = False, # build + describe, do not run (dry run)
           search: Optional[str] = None # RAG over the golden library
           ) -> dict
```

## The envelope (cave() never throws)

| status | when | extra fields |
|---|---|---|
| `construction_error` | the spec is malformed (wrong/missing op or args) | `error`, `hint: "read the cave-<op> skill"` |
| `runtime_error` | it built fine but raised while running | `error` |
| `described` | `describe_only=True` | `description`, `spec` |
| `success` / `error` / … | the run finished (the Link’s `LinkStatus`) | `context`, `error` |
| `goldenized` | `goldenize=True` succeeded | `name`, `path` |
| `ok` | a `search=...` query | `matches` |

`construction_error` (you built the spec wrong) is deliberately distinct from `runtime_error` (it ran
and broke), and the construction hint names the exact skill to read.

## Spec format

A spec is a tree of `{"op": "<name>", ...}` nodes; `cave()` builds it recursively and runs it. Each
`cave-<pattern>` skill (and its `reference.md`) gives that pattern’s op shape. List every op with
`registered_ops()`.

```python
spec = {"op": "seq", "links": [
    {"op": "par", "links": [{"op": "agent", "name": "a"}, {"op": "agent", "name": "b"}]},
    {"op": "agent", "name": "c"}]}
await cave(spec, context={"goal": "..."})
await cave(spec, describe_only=True)   # dry run
```

## The proven-team (golden) library

```python
await cave(spec, name="ship_crew", save=True)   # propose -> .cave/quarantine/ship_crew.json
await cave(goldenize=True, name="ship_crew")     # YOU approve -> .cave/golden/ship_crew.json
await cave(search="ship")                        # find proven teams (RAG over golden)

from cave_teams import golden
release = planner >> golden("ship_crew") >> publish   # reuse in the native DSL
#   …or inside any spec:  {"op": "golden", "name": "ship_crew"}
```

Goldenizing is the **one un-automated arc**: the agent proposes (save → quarantine), the human
approves (goldenize). A goldenized team becomes a callable `{"op":"golden"}` op — that is how the
metacontrol surface grows. Golden/quarantine live in a project-local `.cave/` (override with the
`CAVE_HOME` env var).

## Discovery across projects (for a global cave)

```python
from cave_teams import scan_caves, scan_library
scan_caves(roots: List[str] = ["."], recursive=True) -> List[dict]
#   -> [{"project", "cave", "golden": [...], "quarantine": [...]}]
scan_library(roots: List[str] = ["."], kind="golden"|"quarantine", recursive=True) -> List[dict]
#   -> [{"name", "path", "root", "kind"}]
```

The `roots` you pass **are the boundary** — nothing outside them is touched, heavy dirs
(`node_modules`/`.git`/…) are pruned, and `.cave` is not descended into. A global `.cave` app uses
`scan_caves` to enumerate and federate every cave-enabled project.

## Extending the surface

```python
from cave_teams import register, register_fn, registered_ops, registered_fns
register("my_pattern", lambda s: my_builder(...))   # add a canonical op
register_fn("my_mutator", fn)                         # name a callable (for blackboard/world/season specs)
from cave_teams import build_from_spec                # the recursive builder _build (spec -> Link)
```

The native API is the instruction set; `cave()` is the interpreter; `register`/`register_fn` +
`goldenize` extend the instruction set.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill.
