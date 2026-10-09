---
name: cave-messages
description: The file-message substrate of the leader-driven runtime — a message IS a JSON file, dispatch is a POINTER (never the payload), the session dir is task.txt/leader_outbox/inbox/messages/artifacts. Use when you need to understand how agents actually communicate in a real cave-team run, where the files land on disk, or how the guardrail reads the log. Triggers: "message files", "how do agents talk", "the file spine", "team session dir", "pointer not payload", "cave-messages".
---

# cave-messages — a message is a file (the leader-driven substrate)

This is **the main thing** (cave-teams rule 01). In a real cave-team run, agents do **not** pass
strings to each other in memory — **a message IS a file in the team's dir**, and cave-teams watches
that dir, checks each message against the guardrails, and dispatches only when conditions are met.

> This is the substrate under the **cave-run-team** runtime and the **cave-leader** loop. Read those
> two next; this skill is what they write to disk.

## The unit — `TeamMessage`

One message = one JSON file. The dataclass (`cave_teams.messages.TeamMessage`):

```python
TeamMessage(frm, to, kind=RESPONSE, path="", text="",
            one_liner_to_show_user="", data={}, id=<12-hex>, ts=<time>)
```

- **`kind`** is a small, stable vocabulary (so guardrail conditions can switch on it):
  `DISPATCH` (runtime/leader → agent: a pointer, *"read {path}"*), `RESPONSE` (agent → team: the
  final answer, written into the dir), `FLAG` (a condition flag was set), `DONE` (the team finished).
- **Pointer, not payload.** The big content lives at **`path`** (a file under `artifacts/`); `text`
  stays small (a ~200-char preview). A dispatch says *"read this file"* — it never inlines the
  payload. This is the **never-truncate** rule: a large payload stays a POINTER, never a slice.
- `one_liner_to_show_user` is the human-facing 1-line status the dashboard renders.

## Where the files live — the session dir

`cave_teams.session.TeamSession` lays out one run under `<team_dir>/sessions/<session_id>/`:

```
task.txt              # the task; the leader is told to check it
leader_outbox/        # the leader WRITES its proposed message file here (msg_001.json, …)
inbox/<teammate>/     # DELIVERED (post-guardrail) messages — what each teammate reads
messages/             # the flat team-event LOG (every dispatch + response) — conditions read THIS
artifacts/            # the payloads that message pointers reference (e.g. <name>-response-3.txt)
```

**The guardrail gate sits between `leader_outbox/` (proposed) and `inbox/<teammate>/` (delivered):**
a message is copied into a teammate's inbox **only after it passes the check** (see cave-leader).
`messages/` is the append-only event log — one JSON file per event, named `<ts>-<frm>-<id>.json`,
read in timestamp order. Guardrail conditions read the log to decide whose turn it is.

## The flow of one hand-off

```
leader writes  leader_outbox/msg_007.json   ({"to":"writer","prompt":...,"path":<researcher's artifact>})
      │  cave-teams reads + CHECKS it (guardrail)
      ▼  valid → deliver
inbox/writer/<ts>-<id>.json   +   messages/<ts>-leader-<id>.json   (kind=dispatch)
      │  writer runs, reads the pointed-at file, produces text
      ▼
artifacts/writer-response-4.txt      (the payload)
messages/<ts>-writer-<id>.json       (kind=response, path→that artifact, text=preview)
```

So the information carried between two contacts is a **file path**: the writer's dispatch pointed at
the researcher's artifact file, the writer read it, and its own response is a new artifact. Nothing
is threaded in memory — the dir is the channel. (This is the plane the in-process `>>`/`|` DSL does
NOT use; the DSL threads a Python dict instead — see **cave-teams** and the **cave-runtimes** fork.)

## Why a file and not a string

Pure stdlib, no cave / no pydantic — so the channel is inspectable, replayable, and language-neutral.
cave (the central event system) is *adapted* to watch this dir, so it reacts to **only team events**,
not every LLM event. You can `cat` any run's `messages/` afterward and read exactly what happened —
which is how you verify a team ran correctly (force the actions, then read every file).

## See also
`cave-run-team` (the runtime that writes these) · `cave-leader` (who proposes them + the guardrail) ·
`cave-teams` (the in-process DSL, the OTHER plane). Part of the **cave-teams** plugin.
