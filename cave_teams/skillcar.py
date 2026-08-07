"""
skillcar.py — the CODE-LEVEL car: the ARTIFACT is the genome.

The dark factory's config car (darkfactory.config_kind) tunes knobs; THIS kind
races the artifact itself — a skill document (`.md` text) whose fenced
```python block is its executable core. The delta is a change to the TEXT.
The three verbs (the CarKind contract):

  * race(car)      — execute the artifact against the factory's task BATTERY;
                     fitness = #correct. The battery lives on the KIND, never
                     on the car: the car cannot grade itself (anti-Goodhart).
                     Telemetry reveals FAILING INPUTS ONLY — expected outputs
                     never leave the gate, so a dev seat can see what broke
                     but cannot hardcode the answers it hasn't earned.
  * viability(car) — the QUARANTINE: no executable block, or an artifact that
                     cannot execute a single case (syntax error, crash-on-all,
                     timeout-on-all) = DEATH. Scoring worse is NOT death —
                     better/worse is the RACETRACK's verdict, not the gate's.
  * apply_delta    — {"artifact": <new full text>} replaces the genome
                     (whole-text form of the PR; patch form can come later).

THE JUDGE SLOT IS POLYMORPHIC (the same ep-pair socket as everywhere): the
default executor is a SUBPROCESS — materialize the block into a harness, run it
per case with a timeout, compare output (pure code: the honest gate for
code-bearing skills). For prose skills the same slot takes a FRESH-MODEL
executor (a brand-new LLM session per call, no dev context, sees ONLY the
artifact text + the input) — that is the dark factory's #1 fresh-model
test-gate, and the sound mint for WoS test records (the fix for the
self-minted/forgeable test_id the deity itself flagged in the live WoS run).

Weld to the economy: a SHIPPED artifact is exactly what SkillcraftWorld's
trade_post wants — craft_skill(the artifact) + record_test(minted on the gate's
verdict, not the crafter's word) makes it a tradeable, soundly-tested asset.
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
import tempfile
from typing import Any, Callable, Dict, List, Optional

from .darkfactory import CarKind

_FENCE = re.compile(r"```python\s*\n(.*?)```", re.S)

_HARNESS = """\
import sys
{block}
_text = sys.stdin.read()
sys.stdout.write(str(solve(_text)))
"""


def new_skill_car(artifact: str, name: str = "skill") -> Dict[str, Any]:
    """A fresh artifact car: the genome IS the document text."""
    return {"artifact": artifact, "name": name, "generation": 0, "lineage": []}


def apply_artifact_delta(car: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
    """The PR, whole-text form: delta['artifact'] replaces the genome."""
    cand = {k: v for k, v in car.items() if k != "lineage"}
    if isinstance(delta, dict) and isinstance(delta.get("artifact"), str):
        cand["artifact"] = delta["artifact"]
    cand["generation"] = car.get("generation", 0) + 1
    cand["lineage"] = []
    return cand


def extract_block(artifact: str) -> Optional[str]:
    """The artifact's executable core: the first ```python fenced block."""
    m = _FENCE.search(artifact or "")
    return m.group(1) if m else None


async def subprocess_executor(artifact: str, task_input: str, workdir: str,
                              timeout: float = 5.0) -> Dict[str, Any]:
    """The CODE judge: materialize the block as a harness defining solve(text),
    feed the input on stdin, return {'ok', 'output'|'error'}. A missing block,
    non-zero exit, or timeout is an execution failure — never a crash here."""
    block = extract_block(artifact)
    if block is None:
        return {"ok": False, "error": "no executable python block"}
    hdir = tempfile.mkdtemp(prefix="gate-", dir=workdir)
    hpath = os.path.join(hdir, "harness.py")
    with open(hpath, "w", encoding="utf-8") as f:
        f.write(_HARNESS.format(block=block))
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, hpath,
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)
        out, err = await asyncio.wait_for(
            proc.communicate(task_input.encode()), timeout=timeout)
        if proc.returncode != 0:
            return {"ok": False,
                    "error": (err.decode(errors="replace")[-200:]
                              or f"exit {proc.returncode}")}
        return {"ok": True, "output": out.decode(errors="replace").strip()}
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        return {"ok": False, "error": f"timeout after {timeout}s"}


def skill_kind(battery: List[Dict[str, str]],
               executor: Optional[Callable] = None,
               timeout: float = 5.0, require_block: bool = True,
               name: str = "skill-car") -> CarKind:
    """The artifact CarKind over a task battery [{'input','expected'}, …].
    `executor(artifact, task_input, workdir) -> {'ok', 'output'|'error'}` is the
    polymorphic judge seat (default: the subprocess executor; pass a
    fresh-model executor for prose skills, with require_block=False — a prose
    skill has no fenced code; its executable core IS the instructions)."""
    run = executor or (lambda a, t, w: subprocess_executor(a, t, w,
                                                           timeout=timeout))

    async def _race(car, workdir, tag="run"):
        correct, failing, errors = 0, [], 0
        for case in battery:
            r = await run(car["artifact"], case["input"], workdir)
            if r.get("ok") and r.get("output") == case["expected"]:
                correct += 1
            else:
                failing.append(case["input"])          # inputs ONLY — never expected
                if not r.get("ok"):
                    errors += 1
        return {"tag": tag, "fitness": correct, "cases": len(battery),
                "failing_inputs": failing, "exec_errors": errors,
                "car": {k: v for k, v in car.items() if k != "artifact"}}

    async def _viability(car, workdir):
        if require_block and extract_block(car.get("artifact")) is None:
            return {"alive": False,
                    "cause": "malformed: no executable python block",
                    "telemetry": None}
        if not str(car.get("artifact", "")).strip():
            return {"alive": False, "cause": "malformed: empty artifact",
                    "telemetry": None}
        tel = await _race(car, workdir, tag="quarantine")
        if tel["exec_errors"] == tel["cases"]:         # cannot execute AT ALL
            return {"alive": False,
                    "cause": ("artifact cannot execute: every case errored "
                              "(syntax error / crash / timeout)"),
                    "telemetry": tel}
        return {"alive": True, "cause": "pass", "telemetry": tel}

    return CarKind(race=_race, viability=_viability,
                   apply_delta=apply_artifact_delta, name=name)


__all__ = ["new_skill_car", "apply_artifact_delta", "extract_block",
           "subprocess_executor", "skill_kind"]
