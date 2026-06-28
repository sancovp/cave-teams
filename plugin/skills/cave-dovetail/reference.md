# Dovetail (typed hand-off) — reference

## Signature

```python
from cave_teams import dovetail, DovetailModel
dovetail(a: Link, model: DovetailModel, b: Link, name: str = "dovetail") -> Chain
# a ⋈[D] b  ≡  a ; transform(D) ; b   (operator form: a >> dove(D) >> b)
DovetailModel(name="", expected_outputs: List[str] = [],
              input_map: Dict[str, HermesConfigInput] = {}, file_inputs: Dict[str, str] = {})
```

## Parameters

| param | meaning |
|---|---|
| `a, b` | the two Links the typed joint sits between |
| `expected_outputs` | keys the previous step must have produced; a missing one surfaces as BLOCKED/ERROR |
| `file_inputs` | map a context key -> a file path; the file is loaded into the context (JSON->dict, else str) |
| `input_map` | map named outputs of `a` to named inputs of `b` |

## Examples

```python
from cave_teams.dsl import dove
D = DovetailModel(expected_outputs=["spec"], file_inputs={"plan": "PLAN.md"})
piped = a >> dove(D) >> b
# or by function:
piped = dovetail(a, D, b)
```

## cave() op (drive it from data)

```json
{"op": "dovetail", "a": <spec>, "b": <spec>,
 "model": {"expected_outputs": ["spec"], "file_inputs": {"plan": "PLAN.md"}}}
```

## Notes

The joint validates the previous step’s outputs and prepares the next step’s named inputs (loading files, mapping keys). `file_inputs` over ~10k chars are replaced with a "you must read {path}" instruction instead of inlining. The `cave()` spec covers `expected_outputs` + `file_inputs`; `input_map` (typed HermesConfigInput) is best built in code.

---
Summary + triggers: `SKILL.md` in this folder. The language + full DSL: the **cave-teams** skill. Drive any pattern from data: the **cave** skill.
