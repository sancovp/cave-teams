"""
runner.py — the LEADER-DRIVEN team run (the real execution model, rule 01).

Teams are always a LEADER + teammates. The leader is an intelligent autonomous DOVETAIL: it
receives the task, reasons, and WRITES a message to a teammate. cave-teams does NOT immediately
run the next thing — it CHECKS the written message against the guardrails (does the target exist in
the team? is it that agent's turn? is the format valid?). If invalid, it re-prompts the leader with
the error `{e}` and the leader (an LLM) self-fixes. If valid, cave-teams delivers it, the teammate
runs, and the leader is alerted with the result (how to check it + the message PATH, never inlined,
+ the OPEN-WORLD rules for that step) — then proposes the next message, or ENDS with a report.

Two tiers of between-agent rules:
  - CLOSED-WORLD (enforced): the compiled edge-conditions — member? whose turn? — checked
    mechanically by cave-teams (block + re-prompt with {e}).
  - OPEN-WORLD (`open_rules={agent: [str]}`, NOT enforced): intelligent-reliant rules only the leader
    can judge; cave-teams surfaces them and ASSUMES they hold when the leader invokes the next teammate.

The whole run executes in ONE event loop (so async runtimes share it).
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from .messages import TeamMessage, RESPONSE, DISPATCH
from .session import TeamSession
from .wiring import compile_to_edges


@dataclass
class Proposal:
    """What the leader proposes each step: a message to a teammate, or END (with a report)."""
    to: str = ""
    prompt: str = ""
    path: str = ""
    one_liner: str = ""        # human-facing 1-line status for the dashboard (one_liner_to_show_user)
    end: bool = False
    report: str = ""


# A leader: given the run context (task, history, last alert, any error), propose the next message.
# May be sync (tests) or async (a real LLM). For a real leader this wraps an agent that emits a message.
LeaderFn = Callable[[Dict[str, Any]], Any]


# ── guardrail (closed-world) ────────────────────────────────────────────────
def _responded(to: str, log: List[TeamMessage]) -> bool:
    return any(m.frm == to and m.kind == RESPONSE for m in log)


def _allowed(to: str, edges, log: List[TeamMessage]) -> bool:
    """A teammate may be dispatched iff it has an edge whose guardrail-conditions are met by the
    responses so far (the algebra compiled to guardrails) and it has not already responded."""
    if _responded(to, log):
        return False
    return any(e.to == to and all(c(log) for c in e.conditions) for e in edges)


def _ready(edges, log) -> List[str]:
    return sorted({e.to for e in edges if _allowed(e.to, edges, log)})


def check_proposal(p: Proposal, team_agents: List[str], edges, log) -> Optional[str]:
    """THE GUARDRAIL. Returns an error string `{e}` if the proposal is invalid, else None."""
    if p.end:
        return None
    if not p.to:
        return "You must name a teammate in 'to', or END the run."
    if p.to not in team_agents:
        return f"Agent '{p.to}' is not in this team. Members: {team_agents}."
    if not _allowed(p.to, edges, log):
        ready = _ready(edges, log)
        if not ready:
            return f"It isn't {p.to}'s turn, and no teammate is ready yet."
        return f"It isn't {p.to}'s turn — these can run now: {ready}. Message one of them."
    return None


# ── async invocation helpers (one event loop for the whole run) ─────────────
async def _ainvoke(obj, arg):
    """Call obj.run(arg) / obj(arg); await if it returns a coroutine."""
    out = obj.run(arg) if hasattr(obj, "run") else obj(arg)
    if asyncio.iscoroutine(out):
        out = await out
    return out


async def _run_teammate(rt, prompt: str):
    """Run a teammate; return (output, meta). meta carries the run's identifiers (history_id,
    transcript_path, conversation_id) when the runtime exposes them — so the leader can CHECK the
    work via them, rather than being fed the output."""
    if rt is None:
        return "", {}
    out = await _ainvoke(rt, prompt)
    text = out if isinstance(out, str) else ("" if out is None else str(out))
    meta = {k: getattr(rt, k) for k in ("history_id", "transcript_path", "conversation_id")
            if getattr(rt, k, None) is not None}
    return text, meta


async def _propose(leader: LeaderFn, ctx: Dict[str, Any]) -> Proposal:
    p = leader(ctx)
    if asyncio.iscoroutine(p):
        p = await p
    return p


# ── the run ─────────────────────────────────────────────────────────────────
async def run_team_async(team, task: str, leader: LeaderFn, teammate_runtimes: Dict[str, Any],
                         team_dir, open_rules: Optional[Dict[str, List[str]]] = None,
                         session_id: str = "session", on_event: Optional[Callable] = None,
                         max_steps: int = 100, max_fixes: int = 3) -> Dict[str, Any]:
    open_rules = open_rules or {}
    emit = on_event if on_event else (lambda ev: None)   # team-event stream for the live dashboard
    edges = compile_to_edges(team.build())
    team_agents = sorted({e.to for e in edges})
    s = TeamSession(team_dir, session_id)
    task_path = s.write_task(task)
    log: List[TeamMessage] = []
    transcript: List[dict] = []
    last_alert: Optional[dict] = None

    for _ in range(max_steps):
        ctx = {"task": task, "task_path": task_path, "team_agents": team_agents,
               "outbox": str(s.outbox), "log": [m.to_dict() for m in log],
               "error": None, "alert": last_alert}

        # the leader proposes; on a guardrail error, re-prompt with {e} so the LLM self-fixes
        proposal = await _propose(leader, ctx)
        err = check_proposal(proposal, team_agents, edges, log)
        fixes = 0
        while err is not None and fixes < max_fixes:
            fixes += 1
            transcript.append({"blocked": err, "proposal": {"to": proposal.to, "end": proposal.end}})
            emit({"kind": "blocked", "data": {"error": err}})
            proposal = await _propose(leader, dict(ctx, error=err))
            err = check_proposal(proposal, team_agents, edges, log)
        if err is not None:
            return {"ok": False, "error": f"leader could not produce a valid message: {err}",
                    "transcript": transcript, "messages": [m.to_dict() for m in s.read_log()]}

        if proposal.end:
            emit({"kind": "report", "data": {"text": proposal.report}})
            return {"ok": True, "report": proposal.report, "transcript": transcript,
                    "messages": [m.to_dict() for m in s.read_log()]}

        # VALID → by invoking this teammate the leader ASSERTS the open-world rules for the prior step
        dmsg = TeamMessage(frm="leader", to=proposal.to, kind=DISPATCH,
                           path=proposal.path or task_path, text=proposal.prompt)
        s.deliver(dmsg)          # guardrail passed → copy into the teammate's inbox + log
        log.append(dmsg)
        emit({"kind": "dispatch", "data": {"to": proposal.to, "prompt": proposal.prompt,
              "path": proposal.path or task_path, "one_liner_to_show_user": proposal.one_liner}})

        # in-process: inline the referenced file so a tool-less teammate has the content
        teammate_prompt = proposal.prompt
        if proposal.path and os.path.exists(proposal.path):
            teammate_prompt += f"\n\n--- {os.path.basename(proposal.path)} ---\n" + open(proposal.path).read()
        out, meta = await _run_teammate(teammate_runtimes.get(proposal.to), teammate_prompt)

        rpath = s.write_artifact(f"{proposal.to}-response-{len(log)}.txt", out)
        rmsg = TeamMessage(frm=proposal.to, to="leader", kind=RESPONSE, path=rpath, text=out[:200])
        s.log(rmsg)
        log.append(rmsg)
        emit({"kind": "response", "data": {"frm": proposal.to, "text": out[:300], "one_liner_to_show_user": ""}})

        # the teammate-finished REPORT to the leader: HOW to check the work (ids/metadata), the
        # message PATH to read (NOT inlined), and the OPEN-WORLD rules the leader must verify next.
        last_alert = {
            "finished": proposal.to,
            "message_path": rpath,
            "history_id": meta.get("history_id"),
            "transcript_path": meta.get("transcript_path"),
            "metadata": meta,
            "open_rules": open_rules.get(proposal.to, []),
        }
        transcript.append({"dispatched": proposal.to, "alert": last_alert})

    return {"ok": False, "error": "max_steps reached", "transcript": transcript,
            "messages": [m.to_dict() for m in s.read_log()]}


def run_team(team, task: str, leader: LeaderFn, teammate_runtimes: Dict[str, Any],
             team_dir, open_rules: Optional[Dict[str, List[str]]] = None,
             session_id: str = "session", on_event: Optional[Callable] = None,
             max_steps: int = 100, max_fixes: int = 3) -> Dict[str, Any]:
    """Sync entry point — runs the whole team in ONE event loop (so async runtimes share it)."""
    return asyncio.run(run_team_async(
        team, task, leader, teammate_runtimes, team_dir, open_rules=open_rules,
        session_id=session_id, on_event=on_event, max_steps=max_steps, max_fixes=max_fixes))


# ── the REAL LLM leader: wrap a runtime (.run) so it reasons + emits a message we check ──────
def _parse_proposal(text: str) -> Proposal:
    """Extract the leader's message from its response: the last JSON object — {to, prompt[, path]}
    to dispatch, or {end, report} to finish. Unparseable → empty Proposal (the guardrail rejects it
    → the leader is re-prompted)."""
    for blob in reversed(re.findall(r"\{[^{}]*\}", text or "", re.DOTALL)):
        try:
            obj = json.loads(blob)
        except Exception:
            continue
        if obj.get("end"):
            return Proposal(end=True, report=str(obj.get("report", "")))
        if "to" in obj:
            return Proposal(to=str(obj.get("to", "")), prompt=str(obj.get("prompt", "")),
                            path=str(obj.get("path", "")))
    return Proposal()


def _leader_prompt(ctx: Dict[str, Any]) -> str:
    parts = [
        f"You are the TEAM LEADER. Teammates you may message: {ctx['team_agents']}.",
        f"TASK: {ctx['task']}  (task file: {ctx['task_path']})",
    ]
    a = ctx.get("alert")
    if a:
        line = (f"UPDATE: '{a['finished']}' finished. Its output is at: {a['message_path']} "
                f"(history_id={a.get('history_id')}).")
        if a.get("open_rules"):
            line += f" Before you proceed, YOU must ensure: {a['open_rules']}."
        parts.append(line)
    if ctx.get("error"):
        parts.append(f"YOUR LAST MESSAGE WAS REJECTED: {ctx['error']}  Fix it and resend.")
    parts.append(
        'Reply with ONE JSON object and nothing else. To dispatch: '
        '{"to":"<teammate>","prompt":"<instruction>","path":"<a file for them to use, e.g. a prior '
        'teammate\'s output path, optional>"}. To finish: {"end":true,"report":"<final report>"}.')
    return "\n".join(parts)


def llm_leader(leader_runtime) -> LeaderFn:
    """Wrap an LLM runtime (any object with `.run(str)->str`) as a leader. It is prompted with the
    run context (task, teammates, last finish-report + open rules, any guardrail error), and its
    JSON reply is parsed into a Proposal that run_team then checks + re-prompts on."""
    async def propose(ctx: Dict[str, Any]) -> Proposal:
        out = await _ainvoke(leader_runtime, _leader_prompt(ctx))
        return _parse_proposal(out if isinstance(out, str) else str(out))
    return propose


def file_leader(leader_runtime) -> LeaderFn:
    """A leader that WRITES its message to a FILE (Isaac's spec). Each step it is told to write its
    JSON message to a specific path in the session's leader_outbox using its file-editing tool;
    cave-teams reads that file, parses it, and (in run_team) checks + re-prompts on {e}.

    The leader_runtime MUST have file tools (e.g. MiniMaxRuntime(tools=None) → BashTool+NetworkEditTool).
    """
    counter = {"n": 0}

    async def propose(ctx: Dict[str, Any]) -> Proposal:
        counter["n"] += 1
        path = os.path.join(ctx.get("outbox", "/tmp"), f"msg_{counter['n']:03d}.json")
        prompt = (_leader_prompt(ctx)
                  + f"\n\nWRITE your JSON message (and NOTHING else) to this exact file path using "
                    f"your file-editing tool, then stop: {path}")
        out = await _ainvoke(leader_runtime, prompt)   # the leader writes the file via its tools
        try:
            with open(path) as f:
                p = _parse_proposal(f.read())
            if p.to or p.end:
                return p
        except Exception:
            pass
        # fallback: the leader may have emitted the JSON in its reply instead of writing the file
        return _parse_proposal(out if isinstance(out, str) else str(out))
    return propose
