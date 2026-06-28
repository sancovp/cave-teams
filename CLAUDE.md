# cave-teams

> **THE ONLY SOURCE OF TRUTH for this build is [`THE-ONLY-SOURCE-OF-TRUTH.md`](THE-ONLY-SOURCE-OF-TRUTH.md)** — Isaac's verbatim words. Build to it. Never put your own words in that file (one exception: a line labelled "QUESTION CLAUDE ASKED").

**Read the architecture before touching code — [`.claude/rules/`](.claude/rules/):**
- [`00-source-of-truth.md`](.claude/rules/00-source-of-truth.md) — the law + the build constraints
- [`01-the-pattern.md`](.claude/rules/01-the-pattern.md) — the message state machine (leader → teammates → idle-notify): sequence + state diagrams
- [`02-architecture-layers.md`](.claude/rules/02-architecture-layers.md) — the layers (what cave-teams MAKES vs what cave PROVIDES), the factory, the firehose→team-events adaptation
- [`03-topologies-configs-classes.md`](.claude/rules/03-topologies-configs-classes.md) — the composition layer: a topology's three faces (Class · Link · Config), the closure law (stacking), subclassing

## What cave-teams IS (one paragraph)

cave-teams is a library that **MAKES a cave server**. You pass it **agents to wire** + **conditions on messages** (the state machine) + the **flow**; it builds a `CAVEConfig` → `CAVEAgent` → `CAVEHTTPServer` that instantiates the agents, runs them (on cave's inbox + automations + `paia` hooks), and serves the flow. It **uses cave** (never reimplements cave / SDNA / heaven) and depends on **cave + chain-ontology only**. The `claude -p` + MiniMax agents are an **example instance** — cave runs any agent runtime.

## The pattern (Isaac's words)

There is a **team leader** and a **team**. Messages go **from the leader → one / some / all teammates**. When a teammate **goes idle, it notifies the leader**. That's it — **async**: teammates run while the leader runs, once the leader kicks them off (single message, or broadcast to all/some). The agents run with the **`paia*` hooks** so they hit the cave server.
