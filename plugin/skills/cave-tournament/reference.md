# Tournament / map-reduce (`tournament` / `synthesis_gate`) — reference

## Signature

```python
from cave_teams import tournament, synthesis_gate
tournament(competitors: List[Link], judge: Link, name: str = "tournament") -> Chain
synthesis_gate(workers: List[Link], reducer: Link, name: str = "synthesis") -> Chain
```

## Parameters

| param | meaning |
|---|---|
| `competitors / workers` | Links that run in parallel on the same input |
| `judge / reducer` | the Link that sees every output (`output:<name>` keys) and selects/merges |
| `name` | label |

## Examples

```python
best = tournament([minimalist, bold, nerdy], judge)
merged = synthesis_gate([clarity, punch, honesty], synthesizer)
res = await best.execute({"goal": "write a 6-word tagline"})
res.context["output:judge"]   # the verdict
```

## cave() op (drive it from data)

```json
{"op": "tournament", "competitors": [<spec>, ...], "judge": <spec>}
// or: {"op": "map_reduce", "workers": [<spec>, ...], "reducer": <spec>}
```

## Notes

`tournament` is `synthesis_gate` with the reducer acting as a judge/argmax — N compete in parallel, one selects. The judge/reducer reads the competitors’ outputs from the `output:<name>` keys; assemble them into its prompt (a small "gather" step) so it sees all candidates. In the crafter sim the judge is the **user’s purchase** — the sound external gate. Pairs with **cave-evolve** to breed the winners.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
