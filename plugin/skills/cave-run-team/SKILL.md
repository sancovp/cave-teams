---
name: cave-run-team
description: The leader-driven runtime entry points — run_team (pure, in-process teammates, one event loop) and cave_team (spins up an ephemeral headless CAVE HTTP server + a live /team dashboard, tears it down). Use when you want to actually RUN a real multi-agent team with message files + a leader, not the in-process >>/| DSL. Triggers: "run a real team", "run_team", "cave_team", "ephemeral cave server", "team dashboard", "leader-driven run", "force the agents to run", "cave-run-team".
---

# cave-run-team — running a real leader-driven team

This is the runtime that executes the **leader-driven** plane (the one where messages are files and a
leader routes them). Two entry points, same loop underneath.

> Prereqs: **cave-leader** (who drives it) + **cave-messages** (what it writes to disk). The other
> plane — the in-process `>>`/`|` DSL run by `.execute()` — is **cave-teams**; this is the fork
> called out in **cave-runtimes**.

## The loop (what actually happens)

`run_team_async` (in `cave_teams.runner`) does this, in one event loop:

1. `compile_to_edges(team.build())` → the closed-world guardrails; `team_agents` = the members.
2. Open a `TeamSession` (writes `task.txt`, makes `leader_outbox/ inbox/ messages/ artifacts/`).
3. Loop up to `max_steps`:
   - build `ctx` (task, log, in_flight, last alert, any error) and ask the **leader** to propose;
   - `check_proposal` the proposal — on error, re-prompt the leader with `{e}` (up to `max_fixes`);
   - `end` → emit the report and return; `wait` → block on the next finish;
   - valid dispatch → `deliver` the message into each target's inbox + log it, start each teammate as
     a **concurrent task**, then `_reap_one` (alert the leader as the next teammate finishes).
4. Each teammate's output is written to `artifacts/<name>-response-N.txt`; a `RESPONSE` message
   (pointer to that file) is logged.

## `run_team` — the pure entry point (no server, no cave)

```python
from cave_teams import run_team

res = run_team(
    team,                       # a Team / composed topology (its edges = the guardrails)
    task="build and review X",
    leader=my_leader,           # a LeaderFn — raw | llm_leader(rt) | file_leader(rt)  (see cave-leader)
    teammate_runtimes={"researcher": rt1, "writer": rt2},   # name -> any object with .run(str)
    team_dir="/tmp/myteam",
    open_rules={"researcher": ["cite sources"]},            # optional, leader-judged
    max_steps=100, max_fixes=3,
)
# res: {"ok": bool, "report"|"error": str, "transcript": [...], "messages": [ {...}, ... ]}
```

Sync — it wraps `run_team_async` in a single `asyncio.run` so async runtimes share the loop. **Do not
wrap `run_team` in your own `asyncio.run`** (it already owns the loop). Teammates can be tool-less
(they just return text). Everything is on disk in `team_dir/sessions/session/` afterward — read it.

## `cave_team` — the ephemeral-server runtime (+ live dashboard)

Spins up a **new headless `CAVEHTTPServer`** hosting the leader + teammates as real CAVE agents,
runs the team leader-driven, then tears the server down. Requires `cave` installed.

```python
from cave_teams import cave_team

res = cave_team(
    team,
    agent_runtimes={"researcher": rt1, "writer": rt2},   # teammates (CAVE set_runtime backends)
    leader_runtime=minimax_with_file_tools,              # the leader — needs FILE TOOLS (file_leader)
    task="build and review X",
    leader_name="leader",
    open_rules=None, base_dir="/tmp/cave_teams",
    serve=True, port=None,        # serve=True → a live /team dashboard on a free port
    max_steps=30, linger=0,       # linger>0 keeps the dashboard up after the run for inspection
)
# res adds: res["team_dir"], res["dashboard"] = "http://127.0.0.1:<port>/team?live"
```

- The leader is driven with **`file_leader`** (it writes its JSON message into `leader_outbox/` via
  its file-editing tool). So `leader_runtime` MUST have file tools (e.g. `MiniMaxRuntime(tools=None)`
  → BashTool + NetworkEditTool). Teammates can be tool-less.
- It serves `/team` (a gallery UI) + `/team/events` (a team-event SSE — **only** team events, not
  cave's full LLM firehose). Set `CAVE_TEAMS_GALLERY_URL` to also forward events to a standing app.
- Nested teams (a run launched inside another) inherit a `parent_id` so a gallery can indent them.

## Which entry point

- **`run_team`** — tests, headless CI, when you supply your own runtimes and don't need cave/a UI.
  Pure stdlib channel + your leader. This is what you use to *force every topology to run and then
  read the message files*.
- **`cave_team`** — when you want the real CAVE server + the live dashboard, with CAVE agents and a
  file-writing leader. The production surface.

## Verifying a run (the point)

Both return the full `messages` log and leave `team_dir/sessions/<id>/` on disk. To prove a team ran
correctly: run it, then **read every file** — `messages/*.json` (the event order), `inbox/<t>/`
(what each teammate was actually handed), `artifacts/*` (what each produced), and the `transcript`
(each dispatch, block, and finish-alert). The guardrail blocking an out-of-turn dispatch shows up as
a `{"blocked": "...", ...}` transcript entry — that IS the state machine working.

## See also
`cave-leader` · `cave-messages` · `cave` (drive this from a data spec via the `team_run` op) ·
`cave-teams` (the in-process plane). Part of the **cave-teams** plugin.
