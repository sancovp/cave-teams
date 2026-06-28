#!/usr/bin/env python3
"""
test_minimax_live.py — REAL-LLM smoke test of cave-teams over MiniMax.

Every agent here is a MiniMax agent composed with the cave-teams algebra and run against the live
MiniMax API. Backend is auto-selected:
  • "heaven" (when the heaven framework is present): HeavenMiniMaxLink — the onionmorph/Conductor path
    (HeavenAgentConfig use_uni_api=False + anthropic_api_url from conductor_agent_config.json,
    BaseHeavenAgent.run + BackgroundEventCapture). Self-authenticates — NO env key needed.
  • "bare" (host, if heaven absent): AgentLink(backend="minimax") — needs MINIMAX_API_KEY.
Force with CAVE_BACKEND=heaven|bare.

This is the metaformal self-test: trigger the real substrate (MiniMax), observe the state-change
(real text in the context), let the composition be the oracle.

Run:  python3 test_minimax_live.py [seq|par|tournament|gate|all]   (default: all)
"""
import asyncio
import os
import sys
import time

from cave_teams import AgentLink, synthesis_gate, tournament, eval_chain
from cave_teams.chain_ontology import Link, LinkResult, LinkStatus

# ── backend selection ────────────────────────────────────────────────────────
try:
    import heaven_base  # noqa: F401
    _HEAVEN_AVAILABLE = True
except Exception:
    _HEAVEN_AVAILABLE = False

BACKEND = os.environ.get("CAVE_BACKEND") or ("heaven" if _HEAVEN_AVAILABLE else "bare")
MODEL = os.environ.get("MINIMAX_MODEL", "MiniMax-M2.7-highspeed")


def agent(name: str, system_prompt: str) -> Link:
    """A MiniMax agent as a Link (heaven path in-container, bare-anthropic path on host)."""
    if BACKEND == "heaven":
        from cave_teams import HeavenMiniMaxLink
        return HeavenMiniMaxLink(name, system_prompt=system_prompt)
    return AgentLink(name, system_prompt=system_prompt, backend="minimax", model=MODEL)


# ── a Gather Link: fold all `output:<name>` keys into one prompt for a judge/reducer ──
class Gather(Link):
    """The scatter→reduce joint: collect every competitor's `output:<name>` into one formatted
    block under `output`, so the downstream judge/synthesizer actually SEES all candidates (the
    merged plain `output` only carries the last writer's text)."""

    name = "gather"

    def __init__(self, header: str = "Here are the candidates:"):
        self.header = header

    async def execute(self, context=None, **kwargs):
        ctx = dict(context) if context else {}
        items = {k[len("output:"):]: v for k, v in ctx.items()
                 if k.startswith("output:") and k != "output:gather"}
        ctx["output"] = self.header + "\n\n" + "\n\n".join(
            f"[{n}]\n{str(v).strip()}" for n, v in items.items())
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + "Gather(output:* → output)"


# ── a real-LLM gate: wrap a critic, parse its verdict → ctx['approved'] ──
class VerdictGate(Link):
    """Run a critic agent, then turn its natural-language verdict into the boolean the EvalChain
    gate checks. THIS makes gate-soundness real: status SUCCESS ⟺ the critic literally said
    APPROVE (not a self-granted flag)."""

    name = "verdict_gate"

    def __init__(self, critic: Link, approve_token: str = "APPROVE"):
        self.critic = critic
        self.approve_token = approve_token

    async def execute(self, context=None, **kwargs):
        res = await self.critic.execute(context)
        if res.status != LinkStatus.SUCCESS:
            return res
        ctx = res.context
        verdict = (ctx.get("output") or "")
        ctx["approved"] = self.approve_token.lower() in verdict.lower()
        ctx["verdict"] = verdict
        return LinkResult(status=LinkStatus.SUCCESS, context=ctx)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f"VerdictGate(→{self.critic.name})"


def _hr(title: str):
    print("\n" + "═" * 70 + f"\n  {title}\n" + "═" * 70)


def _show(ctx: dict, *keys: str):
    for k in keys:
        v = ctx.get(k)
        if v:
            print(f"\n  ▶ {k}:\n    " + str(v).strip().replace("\n", "\n    "))


# ───────────────────────────────────────────────────────────────── demos
async def demo_seq():
    _hr("SEQ  ·  a >> b  ·  research → summarize")
    research = agent("researcher",
                     "You are a terse research assistant. Given a topic, list exactly 3 key facts as bullets. Under 80 words.")
    summarize = agent("summarizer",
                      "Rewrite the input as ONE punchy sentence a marketer would use. No preamble.")
    flow = research >> summarize
    print("  expr:\n" + flow.describe())
    t = time.time()
    res = await flow.execute({"goal": "the AGI race between the US and China in 2026"})
    print(f"\n  status={res.status.value}  {int((time.time()-t)*1000)}ms")
    _show(res.context, "output:researcher", "output:summarizer")


async def demo_par():
    _hr("PAR  ·  (a | b | c) >> gather >> synth  ·  3 reviewers fan out, 1 synthesizes")
    tagline = "Compose agents like code."
    lenses = {
        "clarity": "You review taglines for CLARITY only. One sentence verdict + a score /10.",
        "punch":   "You review taglines for emotional PUNCH only. One sentence verdict + a score /10.",
        "honesty": "You review taglines for OVER-CLAIM/honesty only. One sentence verdict + a score /10.",
    }
    reviewers = [agent(k, v) for k, v in lenses.items()]
    synth = agent("synthesizer",
                  "You are given three short reviews of a tagline. Output a final verdict: KEEP or REVISE, and why, in 2 sentences.")
    scatter = reviewers[0]
    for r in reviewers[1:]:
        scatter = scatter | r
    flow = scatter >> Gather("Three reviews of the tagline:") >> synth
    t = time.time()
    res = await flow.execute({"goal": f"Review this tagline: '{tagline}'"})
    print(f"  status={res.status.value}  {int((time.time()-t)*1000)}ms")
    _show(res.context, "output:clarity", "output:punch", "output:honesty", "output:synthesizer")


async def demo_tournament():
    _hr("TOURNAMENT  ·  (N craft ∥) >> gather >> judge  ·  judge selects the best")
    brief = "Write a 6-word tagline for 'cave-teams', a library to compose AI agents like code."
    styles = {
        "minimalist": "You write ultra-minimal taglines. Output ONLY the tagline, 6 words max.",
        "bold":       "You write bold, punchy taglines. Output ONLY the tagline, 6 words max.",
        "nerdy":      "You write taglines for programmers. Output ONLY the tagline, 6 words max.",
    }
    competitors = [agent(k, v) for k, v in styles.items()]
    judge = agent("judge",
                  "You are given three candidate taglines, each tagged [name]. Pick the single BEST. "
                  "Reply 'WINNER: <name>' then one sentence why.")
    scatter = competitors[0]
    for c in competitors[1:]:
        scatter = scatter | c
    flow = scatter >> Gather("Candidate taglines:") >> judge
    t = time.time()
    res = await flow.execute({"goal": brief})
    print(f"  status={res.status.value}  {int((time.time()-t)*1000)}ms")
    _show(res.context, "output:minimalist", "output:bold", "output:nerdy", "output:judge")


async def demo_gate():
    _hr("GATE  ·  μ: writer >> critic, loop until APPROVE  (gate-soundness, real verdict)")
    writer = agent("writer",
                   "Write a single-sentence slogan for a focus/productivity app. If you receive feedback, revise. Output ONLY the slogan.")
    critic = agent("critic",
                   "You are a strict copy critic. If the slogan is cliché or vague, reply 'REJECT:' + one concrete fix. "
                   "If it is genuinely sharp and specific, reply 'APPROVE'. Be hard to please.")
    flow = eval_chain(writer, VerdictGate(critic), max_cycles=3, approval_key="approved")
    t = time.time()
    res = await flow.execute({"goal": "Draft the slogan."})
    ctx = res.context
    print(f"  status={res.status.value}  approved={ctx.get('approved')}  {int((time.time()-t)*1000)}ms")
    print("  → P2 gate-soundness: status SUCCESS ⟺ critic emitted APPROVE")
    _show(ctx, "output:writer", "verdict")  # the approved slogan (artifact) + the critic's verdict


async def demo_tools():
    _hr("TOOLS  ·  agent with BashTool + NetworkEditTool does REAL work (file side-effect)")
    import os, shutil
    if BACKEND != "heaven":
        print("  (skipped — real tool execution requires the heaven backend / in-container)")
        return
    workdir = "/tmp/cave_tool_demo"
    proof = f"{workdir}/proof.txt"
    if os.path.exists(workdir):
        shutil.rmtree(workdir)  # clean slate so the side-effect is unambiguous
    coder = agent("coder",
                  "You are a coding agent with bash and file-edit tools. DO the task for real using your "
                  "tools (do not just describe it), then report what you did in one line.")
    task = (f"Use your tools to: (1) create directory {workdir}; (2) write the file {proof} containing "
            f"EXACTLY this line: CAVE-TEAMS-TOOLS-OK ; (3) run `cat {proof}` to confirm. Then report the contents.")
    t = time.time()
    res = await coder.execute({"goal": task})
    exists = os.path.exists(proof)
    content = open(proof).read().strip() if exists else None
    print(f"  status={res.status.value}  {int((time.time()-t)*1000)}ms")
    print(f"  ▶ REAL SIDE-EFFECT on disk:  {proof}  exists={exists}  content={content!r}")
    ok = exists and content == "CAVE-TEAMS-TOOLS-OK"
    print(f"  → {'✅ PROVEN' if ok else '✗ NOT PROVEN'}: file written by the agent's own tools (not text)")
    _show(res.context, "output:coder")


DEMOS = {"seq": demo_seq, "par": demo_par, "tournament": demo_tournament,
         "gate": demo_gate, "tools": demo_tools}


async def main(which):
    if BACKEND == "bare" and not os.environ.get("MINIMAX_API_KEY"):
        print("✗ bare backend selected but MINIMAX_API_KEY not set.", file=sys.stderr)
        print("  Run where the heaven framework is available (heaven self-auths) or export MINIMAX_API_KEY.", file=sys.stderr)
        sys.exit(2)
    print(f"cave-teams × MiniMax live test  ·  backend={BACKEND}  ·  model={MODEL}")
    names = list(DEMOS) if which in (None, "all") else [which]
    for n in names:
        try:
            await DEMOS[n]()
        except Exception as e:
            print(f"\n  ✗ {n} FAILED: {e}")
    _hr("DONE")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "all"))
