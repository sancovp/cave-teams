---
name: cave-teams-learner
description: The testing machine for cave-teams — force every topology to actually RUN with real LLM agents and read the interactions (message files + histories), not pass/fail flags. Use to verify a topology works, to regression-check the library, or to see a leader-driven / world topology execute end to end. Triggers: "test the topologies", "run every topology", "verify cave-teams", "does this topology actually run", "cave-teams learner", "force the agents to run".
---

# cave-teams-learner — run every topology, read what really happened

The rule this skill enforces (learned the hard way): **the result of a test is not the test. The
test is forcing the actions onto a real LLM and reading every interaction.** Never conclude a
topology "works" or "wanders" from a status flag or a store snapshot — read the message files and the
agent transcripts first. (A tooled worker mid-task looks identical to a stuck one until you read its
history.)

This skill traverses the cave-teams curriculum (`curriculum/cave-teams.manifest.json`) and, for each
topology, RUNS it with real agents, then tallies the actual interactions. It is the systematic
version of ad-hoc probing — the powerset-agent pattern (see `garage-lab/POWERSET-PRINCIPLES.md`).

## The three tools

- **`tools/learner.py`** — the leader-driven plane. Runs each topology with an **automated LLM
  leader** (`llm_leader`) or a **coded leader** (a `leader_fn`), reads the message files + the
  execution stream (dispatch / finish + `still_running`), the guardrail blocks, and the artifacts.
  Nodes: `sequential`, `parallel` (broadcast+reap), `branch` (leader routing), `loop_raw` (coded
  verdict-reading leader), `loop` (the llm-leader loop that exposes the pointer-not-payload finding).
- **`tools/worlds_test.py`** — the world features on tooled agents: `blackboard`, `season`,
  `evolve` (deterministic). Reads the resulting arena/season state.
- **`tools/worlds_features2.py`** — `npc` (call_npc → NPC → inventory) and `nested_worlds`
  (`world_as_agent`). Reads the outer board.

## Run it

```bash
# env: a MiniMax key (env var ONLY — never write it to a file or commit it), a heaven data dir,
# and cave-teams on the path.
MINIMAX_API_KEY=<key> HEAVEN_DATA_DIR=/tmp/heaven-data PYTHONPATH=/path/to/cave-teams \
  python tools/learner.py --only sequential      # one node
MINIMAX_API_KEY=<key> HEAVEN_DATA_DIR=/tmp/heaven-data PYTHONPATH=/path/to/cave-teams \
  python tools/learner.py                          # all leader-driven nodes
MINIMAX_API_KEY=<key> HEAVEN_DATA_DIR=/tmp/heaven-data PYTHONPATH=/path/to/cave-teams \
  python tools/worlds_test.py                      # blackboard · season · evolve
```

Each writes a results JSON and prints the actual interactions. **After a run, read** the printed
execution stream + artifacts (and, for a leader-driven run, `team_dir/sessions/session/messages/*`)
to confirm the topology behaved — that reading IS the verification.

## Hard-won operating rules

- **Read the transcript before concluding.** Heaven leaves an agent's history at
  `$HEAVEN_DATA_DIR/agents/<name>/memories/histories/…`. A worker doing real multi-step work looks
  stuck from the outside; read its turns before calling it broken.
- **Hard-exit your runners** (`os._exit(0)`): heaven leaves non-daemon threads alive, so a plain
  return HANGS the process long past the work finishing (looks "stuck", isn't).
- **Tooled by default:** `MiniMaxRuntime(tools=None)` → BashTool + NetworkEditTool (a real coding
  agent). `tools=[]` is an explicit strip (pure chat) — only for topology-plumbing tests.
- **Don't touch max_tokens** — leave it at the runtime default.

## See also
`cave-teams-volume` (the curriculum) · `curriculum/TOPOLOGY-DIAGRAMS.md` (every topology diagrammed +
its receipt) · `cave-run-team` / `cave-leader` / `cave-messages` (the leader-driven plane it exercises).
Part of the **cave-teams** plugin.
