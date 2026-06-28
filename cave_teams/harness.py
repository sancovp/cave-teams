"""
Harness — message-passing + CONDITION-GATED, CONCURRENT delivery between agents.

THE EXECUTION MODEL (the actor core):
    an agent FIRES when it (a) has a pending message AND (b) passes its conditions.

Conditions are predicates over runtime FLAGS, registered as hooks ("fire when xyz").
A flag flip — or another agent finishing (which auto-sets the flag `done:<agent>`) —
re-evaluates who is now eligible and fires them, each on its own worker thread. So the
TOPOLOGY is DECLARATIVE: a pipeline (A→B→C), a join/barrier (`after("a","b")`), a gated
branch (`when_flag("approved")`) = conditions + flags + message wiring. Eligible agents
run CONCURRENTLY (set `concurrent=False` for deterministic single-threaded runs / tests).

Every boundary streams through the EventBus (events OUT); `send_message` is control IN.
This mirrors CAVE's Automation system (EventAutomation / `depends_on`) but stays STANDALONE;
a condition predicate can wrap a CAVE automation when you want the full machinery
(see conditions.wrap_cave_automation).
"""

import json
import logging
import os
import time
import threading
from collections import deque
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from .conversation import Conversation, Message
from .events import EventBus, FileListener

logger = logging.getLogger(__name__)

# a condition hook: given the harness + the agent name, may this agent fire now?
Condition = Callable[["Harness", str], bool]


class Harness:
    """Condition-gated, concurrent message routing between persistent agent conversations.

    The on-disk FileListener is auto-subscribed (back-compat); any `on_event` you pass is
    a second listener (a frontend watches the team live). `deliver()` remains a direct
    synchronous primitive; the gated/concurrent path is `send_message` → conditions → fire.
    """

    def __init__(self, team_dir: str, on_event: Optional[Callable] = None,
                 concurrent: bool = True):
        self.team_dir = Path(team_dir)
        self.team = self.team_dir.name
        self.msg_dir = self.team_dir / "messages"
        self.state_dir = self.team_dir / "state"
        self.transcript_dir = self.team_dir / "transcripts"
        self.agents: Dict[str, Conversation] = {}
        self._running = False
        self._poll_interval = 0.5
        self._processed: Dict[str, int] = {}

        for d in [self.msg_dir, self.state_dir, self.transcript_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # The seam: one EventBus per team. Files become just the first listener.
        self.bus = EventBus(self.team)
        self.bus.subscribe(FileListener(str(self.team_dir)))
        if on_event is not None:
            self.bus.subscribe(on_event)

        # --- condition-gated concurrent execution ---
        self.concurrent = concurrent
        self.flags: Dict[str, Any] = {}                 # runtime state the conditions read
        self._conditions: Dict[str, List[Condition]] = {}
        self._routes: Dict[str, List[Tuple[str, Optional[Callable], Optional[Condition]]]] = {}
        self._watchers: Dict[str, List[Callable]] = {}  # output → state bridge (set flags from a reply)
        self._drain: set = set()                        # gather agents: consume ALL pending at once
        self._pending: Dict[str, Deque[Tuple[str, str]]] = {}
        self._busy: Dict[str, bool] = {}
        self._lock = threading.RLock()                  # guards flags/conditions/routes/pending/busy
        self._file_lock = threading.Lock()              # serializes shared file appends

    def register(self, name: str, conversation: Conversation):
        self.agents[name] = conversation
        self._processed[name] = 0
        self._pending.setdefault(name, deque())
        self._busy.setdefault(name, False)
        self._set_state(name, "idle")
        self.bus.emit("agent_added", agent=name, backend=conversation.backend,
                      model=getattr(conversation, "model", None))
        logger.info("Registered agent: %s (%s)", name, conversation.backend)

    # ============================ conditions / flags (the gate; hooks) ============================
    def set_flag(self, name: str, value: Any = True) -> None:
        """Set a runtime flag and re-evaluate who can now fire. The lever that drives topology."""
        with self._lock:
            self.flags[name] = value
        self.bus.emit("flag", agent="", flag=name, value=value)
        self._dispatch_ready()

    def get_flag(self, name: str, default: Any = None) -> Any:
        with self._lock:
            return self.flags.get(name, default)

    def add_condition(self, agent: str, predicate: Condition) -> Condition:
        """Register a fire-gate hook for `agent`. It fires only when ALL its conditions pass.
        predicate(harness, agent) -> bool. (See cave_teams.conditions for when_flag/after/when.)"""
        with self._lock:
            self._conditions.setdefault(agent, []).append(predicate)
        return predicate

    def check_conditions(self, agent: str) -> bool:
        with self._lock:
            preds = list(self._conditions.get(agent, []))
        for pred in preds:
            try:
                if not pred(self, agent):
                    return False
            except Exception:
                return False
        return True

    def add_route(self, src: str, dst: str,
                  transform: Optional[Callable[[str], str]] = None,
                  when: Optional[Condition] = None) -> None:
        """EDGE: when `src` finishes a turn, send its output to `dst`.

        `transform(text) -> text` reshapes the message (default: pass through). `when(harness, src)`
        is an optional EDGE condition checked at routing time — only fire this edge if it returns
        True (conditional routing / branch). Edges are how topology flows; conditions (add_condition)
        gate whether a NODE may fire. Together they are the whole control flow.
        """
        with self._lock:
            self._routes.setdefault(src, []).append((dst, transform, when))

    def wire_chain(self, names: List[str]) -> Tuple[str, str]:
        """Wire a sequential HARNESS chain (route names[i] -> names[i+1]); return (head, tail).
        This is the message-passing/condition-gated sequential wiring (used by as_agent for sub-teams),
        distinct from cave_teams.topologies which composes chain-ontology Links."""
        for a, b in zip(names, names[1:]):
            self.add_route(a, b)
        return (names[0], names[-1]) if names else ("", "")

    def add_watch(self, agent: str, fn: Callable[["Harness", str, str], None]) -> None:
        """OUTPUT → STATE bridge: after `agent` replies, run fn(harness, agent, text). The watch may
        set flags from the reply — e.g. flip a stop flag when a critic says 'APPROVED' (ends a loop),
        or count rounds. This is how LLM output conditions control flow."""
        with self._lock:
            self._watchers.setdefault(agent, []).append(fn)

    def set_drain(self, agent: str, on: bool = True) -> None:
        """GATHER mode: when `agent` fires, it consumes ALL its pending messages combined into one
        input (instead of one at a time). Used by synthesis/join agents that need every input."""
        with self._lock:
            (self._drain.add if on else self._drain.discard)(agent)

    # ============================ files ============================
    def _msg_path(self, agent_name: str) -> Path:
        return self.msg_dir / f"{agent_name}.jsonl"

    def _set_state(self, agent_name: str, state: str, extra: dict = None):
        data = {"agent": agent_name, "state": state, "ts": time.time()}
        if extra:
            data.update(extra)
        (self.state_dir / f"{agent_name}.json").write_text(json.dumps(data))

    def _append_msg(self, to: str, from_: str, content: str):
        path = self._msg_path(to)
        entry = {"from": from_, "content": content, "ts": time.time()}
        with self._file_lock:                          # concurrent agents may target one inbox
            with open(path, "a") as f:
                f.write(json.dumps(entry) + "\n")

    def _read_new_messages(self, agent_name: str) -> List[dict]:
        path = self._msg_path(agent_name)
        if not path.exists():
            return []
        lines = path.read_text().splitlines()
        already = self._processed.get(agent_name, 0)
        new_lines = lines[already:]
        self._processed[agent_name] = len(lines)
        messages = []
        for line in new_lines:
            if line.strip():
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return messages

    # ============================ ingest + gated concurrent dispatch ============================
    def _ingest(self, name: str) -> None:
        """Pull any new inbox-file lines for a REGISTERED agent into its pending queue."""
        if name not in self.agents:
            return
        with self._lock:
            msgs = self._read_new_messages(name)
            for m in msgs:
                self._pending.setdefault(name, deque()).append((m.get("from", ""), m.get("content", "")))
        for m in msgs:
            self.bus.emit("message", agent=name, frm=m.get("from", ""), content=m.get("content", ""))

    def send_message(self, from_: str, to: str, content: str) -> None:
        """control IN: queue a message for `to`; it FIRES when its conditions pass.

        Writes the durable inbox line (so external readers / the file log see it), then — for a
        registered agent — ingests + dispatches (condition-gated, concurrent). For an unregistered
        recipient (e.g. an external `claude -p` leader that reads its own inbox) it just logs.
        """
        self._append_msg(to, from_, content)
        if to in self.agents:
            self._ingest(to)
            self._dispatch_ready()
        else:
            self.bus.emit("message", agent=to, frm=from_, content=content)

    def _dispatch_ready(self) -> None:
        """Fire every agent that has a pending message AND passes conditions AND isn't busy.
        Eligible agents run concurrently (own worker thread) unless self.concurrent is False."""
        ready: List[Tuple[str, str, str]] = []
        with self._lock:
            for agent, q in list(self._pending.items()):
                if (agent in self.agents and q and not self._busy.get(agent, False)
                        and self.check_conditions(agent)):
                    self._busy[agent] = True
                    if agent in self._drain and len(q) > 1:   # gather: combine ALL pending inputs
                        items = [q.popleft() for _ in range(len(q))]
                        frm = items[0][0]
                        content = "\n\n---\n\n".join(f"[from {f}]\n{c}" for f, c in items)
                    else:
                        frm, content = q.popleft()
                    ready.append((frm, agent, content))
        for frm, agent, content in ready:
            if self.concurrent:
                threading.Thread(target=self._run_delivery, args=(frm, agent, content),
                                 daemon=True).start()
            else:
                self._run_delivery(frm, agent, content)

    def _run_delivery(self, from_: str, to: str, content: str) -> None:
        """Run one gated delivery; on completion set `done:<agent>` and redispatch.

        The agent's response is appended to the sender's inbox (durable, for the leader /
        orchestration to read) but does NOT auto-fire anyone — firing stays EXPLICIT (you send,
        or a flag flips). That keeps the actor model loop-free: A→B does not make B's reply
        re-fire A. Completion sets `done:<agent>`, which may satisfy other agents' conditions.
        """
        text = None
        try:
            text = self.deliver(from_, to, content)
        finally:
            with self._lock:
                self._busy[to] = False
                self.flags[f"done:{to}"] = int(self.flags.get(f"done:{to}", 0)) + 1
                self.flags[f"output:{to}"] = text          # last reply, readable by conditions/watches
                done_count = self.flags[f"done:{to}"]
                routes = list(self._routes.get(to, []))
                watchers = list(self._watchers.get(to, []))
            self.bus.emit("flag", agent=to, flag=f"done:{to}", value=done_count)
            if text is not None:
                # OUTPUT → STATE: watches may set flags from the reply (ends loops, counts rounds, …)
                for w in watchers:
                    try:
                        w(self, to, text)
                    except Exception:
                        pass
                # fire outgoing EDGES: this agent's output flows to its successors (edge-gated)
                for dst, transform, cond in routes:
                    try:
                        if cond is None or cond(self, to):
                            self.send_message(to, dst, transform(text) if transform else text)
                    except Exception:
                        pass
            self._dispatch_ready()          # completion may unblock other agents' conditions

    def deliver(self, from_: str, to: str, content: str) -> Optional[str]:
        """Call agent with content, write response to sender's inbox. Synchronous primitive
        (the gated/concurrent path calls this under the hood; also usable directly)."""
        agent = self.agents.get(to)
        if not agent:
            logger.error("Agent %s not found", to)
            self.bus.emit("error", agent=to, error="agent not found", frm=from_)
            return None

        self._set_state(to, "processing", {"from": from_})
        self.bus.emit("dispatched", agent=to, frm=from_, content=content)
        logger.info("[%s → %s] Delivering (%d chars)", from_, to, len(content))
        # token-level streaming: each delta becomes a 'stream' event tagged with this agent
        on_chunk = lambda delta: self.bus.emit("stream", agent=to, delta=delta)
        result = agent.send(content, from_agent=from_, on_chunk=on_chunk)
        self._set_state(to, "idle")

        if result.success:
            # leave a durable reply ONLY for an UNREGISTERED sender (the external leader reading its
            # inbox). Registered peers receive replies via explicit routes → avoids double-firing.
            if from_ not in self.agents:
                self._append_msg(from_, to, result.text)
            self._save_transcript(to, from_, content, result)
            self.bus.emit("response", agent=to, to=from_, text=result.text,
                          duration_ms=result.duration_ms)
            logger.info("[%s → %s] Response (%dms, %d chars)",
                        to, from_, result.duration_ms, len(result.text))
            return result.text
        else:
            logger.error("[%s] Error: %s", to, result.error)
            if from_ not in self.agents:
                self._append_msg(from_, to, f"ERROR: {result.error}")
            self.bus.emit("error", agent=to, error=result.error, frm=from_)
            return None

    def _save_transcript(self, agent: str, from_: str, prompt: str, result):
        path = self.transcript_dir / f"{agent}.jsonl"
        entry = {
            "ts": time.time(),
            "from": from_,
            "prompt": prompt[:1000],
            "response": result.text[:2000],
            "duration_ms": result.duration_ms,
            "history_len": self.agents[agent].history_length(),
        }
        with self._file_lock:
            with open(path, "a") as f:
                f.write(json.dumps(entry) + "\n")

    # ============================ watch loop ============================
    def poll_once(self):
        """Ingest any externally-written inbox lines (e.g. a leader's bash echo) → gated dispatch."""
        for name in list(self.agents.keys()):
            self._ingest(name)
        self._dispatch_ready()

    def start(self, blocking: bool = True):
        """Start the watcher loop. Picks up externally-written messages and fires on condition."""
        self._running = True
        logger.info("Harness started. Watching %s", self.msg_dir)

        if blocking:
            self._watch_loop()
        else:
            t = threading.Thread(target=self._watch_loop, daemon=True)
            t.start()
            return t

    def stop(self):
        self._running = False

    def _watch_loop(self):
        while self._running:
            try:
                self.poll_once()
            except Exception as e:
                logger.error("Harness poll error: %s", e, exc_info=True)
            time.sleep(self._poll_interval)

    def wait_idle(self, timeout: float = 30.0, poll: float = 0.02) -> bool:
        """Block until no agent is busy and no agent has a pending message (concurrent runs/tests)."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                idle = (not any(self._busy.values())
                        and all(len(q) == 0 for q in self._pending.values()))
            if idle:
                return True
            time.sleep(poll)
        return False

    def get_all_states(self) -> Dict[str, dict]:
        states = {}
        for name in self.agents:
            path = self.state_dir / f"{name}.json"
            if path.exists():
                states[name] = json.loads(path.read_text())
            else:
                states[name] = {"agent": name, "state": "unknown"}
        return states
