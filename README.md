# cave-teams

**Programmable, leader-driven agent teams on [CAVE](https://pypi.org/project/cave-harness/).**

Run many agent "teams" — a **team leader** that orchestrates **teammates** — without Claude Code Teams' blockers, reuse them, and use **MiniMax or Claude (or any runtime)**, from Claude Code. cave-teams **uses CAVE** (it doesn't reimplement it): each team **makes an ephemeral CAVE server** that hosts the agents, runs them, and serves the flow, then tears it down.

```bash
pip install cave-teams          # pulls cave-harness (the CAVE runtime) + pydantic
```

## The model

Teams are always a **leader + teammates**:

1. The **task** arrives as a file in the team's session dir; the leader checks it.
2. The leader — *an intelligent autonomous dovetail* — **writes a message** to a teammate (often just *"read {path}"*).
3. cave-teams does **not** blindly run the next thing. It **checks the message** against the **guardrails** (is the target in the team? is it that agent's turn? is the format valid?). If it's wrong, it **re-prompts the leader with the error** — and the LLM **fixes itself**. If it's right, it delivers it; the teammate runs; the leader is alerted.
4. The leader decides the next message, or **ends the run and returns a report**.

**Conditions on messages** come in two tiers:

- **Closed-world** (enforced by cave-teams): turn order, membership, format — compiled from the team's algebra.
- **Open-world** (`open_rules`): intelligent-reliant checks only the leader can judge; cave-teams surfaces them and *assumes* they hold when the leader invokes the next teammate.

## Quickstart

```python
from cave_teams import Team, AgentRef, seq, cave_team
from cave_teams.examples import MiniMaxRuntime

class Brief(Team):                       # a topology = a Team subclass (Class · Link · Config)
    op = "brief"
    def build(self):
        return seq(AgentRef("researcher"), AgentRef("writer"))

leader = MiniMaxRuntime("leader", tools=None)            # writes its message files (needs file tools)
teammates = {
    "researcher": MiniMaxRuntime("researcher", tools=[]),
    "writer":     MiniMaxRuntime("writer", tools=[]),
}

result = cave_team(
    Brief({}), agent_runtimes=teammates, leader_runtime=leader,
    task="Topic: why octopuses are intelligent.",
    open_rules={"researcher": ["research must be accurate before the writer uses it"]},
)
print(result["report"])
```

A backend is **any object with `.run(str) -> str`** — that's all `set_runtime` needs. The MiniMax/Claude backends are just an *example instance*; CAVE runs any agent runtime.

## The algebra

Compose teammates with a tiny algebra; it compiles to the guardrails (whose turn it is):

```python
seq(a, b)          # a then b           a >> b
par(a, b)          # a and b together   a | b
gate(body, phi)    # loop until phi
choice(routes)     # guarded branch
team(G)            # a composition as one Link → a team is a teammate (closure law)
```

Topologies are also **configs** (save under `.cave/golden/`, reuse, `scan_caves`) and **classes** (subclass a `Team`, override `build()`).

## Lower-level run

`run_team(team, task, leader, teammate_runtimes, team_dir, open_rules=...)` is the leader-driven loop directly (no CAVE server). `llm_leader(rt)` / `file_leader(rt)` wrap a runtime as the leader (the latter writes its message as a file, per the session/inbox structure). `cave_team(...)` is `run_team` on a freshly-made, torn-down CAVE server.

## Requires

- **`cave-harness`** (the CAVE runtime; import name `cave`) — pulled in automatically.
- For the MiniMax/Claude example backends: the heaven framework + `MINIMAX_API_KEY` in the environment.

MIT.
