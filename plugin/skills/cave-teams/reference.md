# cave-teams — full API reference

Everything below is a `Link` (carrier of the algebra): anything with
`async execute(context: dict) -> LinkResult`. A `Link` reads its input from the context and writes
`output` + `output:<name>`. `import cave_teams` installs the `>>` and `|` operators on `Link`.

## Leaves (agents)

| Constructor | What it is |
|---|---|
| `AgentLink(name, system_prompt="", backend="minimax", model=None, input_key=None, output_key="output")` | A single model agent. `backend="claude-p"` → runs `claude -p` (Opus/Sonnet); `backend="minimax"` → MiniMax via the Anthropic-compatible API. |
| `HeavenMiniMaxLink(name, system_prompt="", tools=None, max_tool_calls=25)` | A real coding agent on the heaven runtime. Default tools = `[BashTool, NetworkEditTool]` (runs bash, edits files). `tools=[]` for a text-only agent. |
| `lift(obj)` / `as_link(obj)` | Wrap ANY runnable (a callable, a `.send`/`.run` object, an SDNA agent) into a Link — the provider-agnostic adapter. |

## Operators (the algebra)

| Call | Symbol | Meaning |
|---|---|---|
| `seq(a, b, …)` / `a >> b` | `;` | sequential — run in order, thread the context |
| `par(a, b, …)` / `a \| b` | `∥` | parallel — run concurrently, merge outputs (`output:<name>` keys + `_concurrent` list) |
| `gate(body, phi, max_cycles=3, approval_key="approved")` | `μ` | run `body`, then evaluator `phi`; loop until `phi` sets `ctx[approval_key]` truthy, or `max_cycles`. Always terminates. |
| `choice(routes, default=None)` | `+` | guarded branch — first `(predicate, link)` whose `predicate(ctx)` is True |
| `dovetail(a, model, b)` / `a >> dove(D) >> b` | `⋈` | typed data-flow joint — `a ; transform(D) ; b` |
| `team(G, name="team")` | — | wrap composition `G` as one named Link (homoiconic closure: `run(team(G)) == run(G)`) |
| `skip()` | `1` | identity Link (unit of `;` and `∥`) |

## Topology builders (built on the algebra)

| Call | Pattern |
|---|---|
| `pipeline(*links)` / `chain(*links)` | sequential chain (same as `>>`) |
| `fan_out(*links)` / `broadcast(*links)` | parallel scatter (same as `\|`) |
| `synthesis_gate(workers, reducer)` / `map_reduce(...)` | scatter → reduce. The reducer sees `output:<worker>` keys. |
| `tournament(competitors, judge)` | N compete in parallel, a judge selects. (Gather the candidates' `output:<name>` into the judge's prompt — the merged `output` only holds the last writer.) |
| `eval_chain(body, evaluator, max_cycles=3)` / `loop_refine(worker, critic)` | evaluator loop (the `gate` builder) |
| `round_robin(links, rounds=1)` | turn-taking |
| `router(routes, default=None)` | conditional branch (the `choice` builder) |
| `blackboard(agents, mutator, deity)` | stigmergy arena: N agents ↔ shared state ↔ adjudicator |
| `evolve(winners, out)` / `evolve_dir(...)` / `select_winners(...)` | genetic step: copy winners' dirs, wipe session memory, regrow |
| `season(...)` / `carry_reset_ratchet(...)` | bounded epoch: carry / reset / ratchet the standard |
| `crafter_sim(...)` | the Economic Crafter Sim: compete → user-buys → select → evolve |

## Worlds

| Call | Meaning |
|---|---|
| `GameWorld(spec, agents, mutator, …)` / `GameWorld.from_spec(spec, agents, mutator)` | a whole world (arena + gate + season) as one composable object — a Link, and a subclassable class |
| `world_as_agent(world)` | present a world as a single player → worlds nest in worlds |
| `npc_mutator(...)` | an NPC players can call via a skill (an NPC can be a whole GameWorld) |

## Running

```python
result = await flow.execute({"goal": "..."})   # the entry context; goal/input is the first input
result.status            # LinkStatus.SUCCESS | ERROR | BLOCKED
result.context           # dict: "output", "output:<name>" per agent, "_concurrent" after a parallel
result.error             # set when status != SUCCESS
print(flow.describe())   # pretty-print the composition tree
```

## The gate, correctly (gate-soundness)

`gate`/`eval_chain` checks `ctx[approval_key]` after the evaluator runs. A plain agent only writes
text, so wrap the critic so its verdict becomes the boolean:

```python
from cave_teams.chain_ontology import Link, LinkResult, LinkStatus

class VerdictGate(Link):
    name = "verdict_gate"
    def __init__(self, critic, approve_token="APPROVE"):
        self.critic = critic
    async def execute(self, context=None, **k):
        res = await self.critic.execute(context)
        ctx = res.context
        ctx["approved"] = "approve" in (ctx.get("output") or "").lower()
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

draft = gate(writer, VerdictGate(critic))   # SUCCESS  ⟺  the critic actually approved
```

## Verified laws (the connectors come with tests)

- `(a >> b) >> c  ≡  a >> (b >> c)` — associativity (structural)
- gate always halts in ≤ `max_cycles` (termination)
- gate `SUCCESS ⟺ approval_key set` (gate-soundness)
- `a;(b+c) ≡ (a;b)+(a;c)` (distribution)

Run the laws yourself: `test_algebra_laws.py`, `test_agent_proofs.py` in the cave-teams package.

## Conditions — the message state machine

Program WHEN each agent runs (the part Claude Code Teams can't do). The `Harness` fires an agent when
it has a pending message AND its conditions over runtime flags pass:

```python
from cave_teams import Harness, when_flag, after, when
h = Harness(team_dir, concurrent=False)
h.add_condition("publisher", when_flag("approved"))     # only after approval
h.add_condition("merge", after("frontend", "backend"))   # join — wait for both
h.add_condition("worker", when(lambda hh, a: hh.get_flag("budget") > 0))
```

See the **cave-conditions** skill. This is the message *runtime*, not a composition Link.

## The metacontrol function + golden library

`cave()` drives the whole API from a data spec (NOT how you normally program — the DSL above is). It
also holds the proven-team library:

```python
from cave_teams import cave, golden, scan_caves
await cave({"op": "seq", "links": [...]}, context={"goal": "..."})   # run a team from data
await cave(spec, name="ship_crew", save=True)                       # save  -> .cave/quarantine/
await cave(goldenize=True, name="ship_crew")                        # approve -> .cave/golden/
release = planner >> golden("ship_crew") >> publish                # reuse a proven team
scan_caves(roots=["~/work"])                                        # find every .cave project
```

See the **cave** skill + its `reference.md`.

## Per-pattern references

Each pattern has its own `SKILL.md` (trigger + summary) and `reference.md` (full signature, params,
the `cave()` op, gotchas):

`cave-sequential` · `cave-parallel` · `cave-branch` · `cave-gate` · `cave-conditions` ·
`cave-dovetail` · `cave-dag` · `cave-blackboard` · `cave-tournament` · `cave-evolve` ·
`cave-season` · `cave-world` · `cave-sim` · `cave-metacog` — and **cave** for the metacontrol.
