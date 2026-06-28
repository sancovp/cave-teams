# Gate (`gate` / `eval_chain` / `loop_refine`) — reference

## Signature

```python
from cave_teams import gate, eval_chain, loop_refine
gate(body: Link, phi: Link, max_cycles: int = 3,
     approval_key: str = "approved", name: str = "gate") -> EvalChain
loop_refine(worker: Link, critic: Link, max_cycles: int = 3,
            approval_key: str = "approved", name: str = "loop_refine") -> EvalChain
```

## Parameters

| param | meaning |
|---|---|
| `body / worker` | the Link(s) to run each cycle |
| `phi / critic` | the evaluator; it must set `context[approval_key]` truthy to approve |
| `max_cycles` | hard cap on iterations (guarantees termination) |
| `approval_key` | the context key the evaluator sets (default `"approved"`) |

## Examples

```python
# wrap a critic so its verdict becomes the approved flag:
class VerdictGate(Link):
    def __init__(self, critic): self.name="vg"; self.critic=critic
    async def execute(self, context=None, **k):
        r = await self.critic.execute(context); ctx = r.context
        ctx["approved"] = "APPROVE" in (ctx.get("output") or "")
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)
draft = gate(writer, VerdictGate(critic), max_cycles=3)
```

## cave() op (drive it from data)

```json
{"op": "gate", "body": <spec>, "evaluator": <spec>, "max_cycles": 3, "approval_key": "approved"}
// or: {"op": "loop", "worker": <spec>, "critic": <spec>, "max_cycles": 3}
```

## Notes

**Two proven laws** (mechanically tested):
- **P1 termination** — the loop halts in `≤ max_cycles`.
- **P2 gate-soundness** — final status is SUCCESS **iff** the evaluator set `approved` (a passed gate really was approved).

**Gotcha:** a plain agent writes text, not the `approved` flag. You must wrap the evaluator so its verdict sets `context["approved"]` (see the example) — otherwise the gate never approves and runs to `max_cycles`.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
