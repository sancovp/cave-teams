"""
cave-teams LEARNER — the curriculum-driven test harness (Part B).

Walks the leader-driven curriculum and, for each topology, RUNS it with a real AUTOMATED LLM leader
(llm_leader — a MiniMax agent in the leader seat, the untested type-3), then reads the actual
file-spine (messages/, artifacts/) and reports what really happened: every dispatch, every response
in guardrail-enforced order, every BLOCK the guardrail issued, and a per-node verdict + a mermaid
sequence. Nothing here asserts a canned result — it forces the actions onto the LLM and tallies them.
"""
import os, sys, json, time, argparse

sys.path.insert(0, os.path.expanduser("~/repo/cave-teams"))
from cave_teams.team import Team
from cave_teams.wiring import AgentRef
from cave_teams import algebra
from cave_teams.runner import run_team, llm_leader, Proposal
from cave_teams.examples import MiniMaxRuntime

SD = os.path.dirname(os.path.abspath(__file__))
RUNROOT = os.path.join(SD, "LEARNER_RUNS")
T0 = time.time()
def log(m): print(f"[{time.time()-T0:6.1f}s] {m}", flush=True)


def mk(name, sp):
    return MiniMaxRuntime(name, tools=[], system_prompt=sp)


# ── the leader-driven curriculum nodes (topology → a real run) ───────────────
def teammate(sp): return sp


def make_loop_leader():
    """A CODED leader (one of the 3 leader types) that READS the critic's verdict file and ENDS on
    APPROVED — the verdict-gated loop a tool-less automated leader cannot do (pointer-not-payload)."""
    def leader(ctx):
        alert = ctx.get("alert")
        if alert and alert.get("finished") == "critic":
            verdict = open(alert["message_path"]).read()
            if "APPROVED" in verdict.upper()[:60]:
                return Proposal(end=True, report="critic APPROVED — loop terminated on verdict. "
                                                 + verdict.strip().replace("\n", " ")[:140])
            return Proposal(to="writer", prompt="The critic REJECTED it. Revise to satisfy the "
                            "feedback in the file.", path=alert["message_path"])
        if alert and alert.get("finished") == "writer":
            return Proposal(to="critic", prompt="Judge this couplet; reply APPROVED or REJECTED.",
                            path=alert["message_path"])
        return Proposal(to="writer", prompt="Write the couplet.", path=ctx.get("task_path", ""))
    return leader


TOPOLOGIES = {
    # 0.2.1 sequential — researcher then writer; guardrail must enforce order even if the LLM leader
    # tries to jump ahead. Proves: automated LLM leader (type-3) + the file spine + order enforcement.
    "sequential": dict(
        op="curriculum_sequential",
        build=lambda: algebra.seq(AgentRef("researcher"), AgentRef("writer")),
        teammates={
            "researcher": "You are a researcher. When messaged, output EXACTLY 2 concrete facts "
                          "(each with a number or named entity) about the topic. No preamble.",
            "writer": "You are a writer. You will be given the researcher's facts. Write ONE "
                      "sentence that explicitly reuses at least one specific number/entity from them.",
        },
        task="Produce a one-sentence blurb about honeybees, grounded in researched facts. "
             "The researcher must go first; the writer uses the researcher's output.",
    ),
    # 0.2.2 parallel — three reviewers with NO order constraint (par edges → all ready at once).
    # Proves: concurrent BROADCAST (dispatch to a SET at once) + reap-as-each-finishes (still_running).
    "parallel": dict(
        op="curriculum_parallel",
        build=lambda: algebra.par(AgentRef("security"), AgentRef("perf"), AgentRef("tests")),
        teammates={
            "security": "You are a security reviewer. In 2 short bullets, name concrete security "
                        "risks of the code/feature described. Be specific.",
            "perf": "You are a performance reviewer. In 2 short bullets, name concrete performance "
                    "concerns of the code/feature described.",
            "tests": "You are a test reviewer. In 2 short bullets, name concrete missing tests for "
                     "the code/feature described.",
        },
        task="Review this feature on ALL THREE dimensions AT THE SAME TIME (security, perf, tests): "
             "'a new /login endpoint that checks a password against a users table and returns a JWT'. "
             "The three reviewers have no ordering between them — dispatch them together.",
    ),
    # 0.2.5 gate → leader-driven LOOP. gate() does NOT compile to edges (branching/iteration is the
    # leader's job). Team is seq(writer, critic); the leader RE-DISPATCHES writer on rejection (the
    # guardrail explicitly allows re-dispatch to an already-responded agent) until the critic APPROVES.
    # Proves: leader-driven iteration (item #4 loop) + revision loops through the guardrail.
    "loop": dict(
        op="curriculum_loop",
        build=lambda: algebra.seq(AgentRef("writer"), AgentRef("critic")),
        teammates={
            "writer": "You are a writer. Write a two-line rhyming couplet where each line has between "
                      "six and ten words. If you are given critic feedback, revise to satisfy it. "
                      "Output only the two lines.",
            "critic": "You are a critic. You are given a two-line couplet. Reply APPROVED if the two "
                      "lines rhyme and each line has between six and ten words; otherwise reply "
                      "REJECTED and say exactly what to fix. Start with the single word APPROVED or "
                      "REJECTED.",
        },
        task="Produce a two-line rhyming couplet, each line six-to-ten words. LOOP: send the writer's "
             "draft to the critic; if the critic replies REJECTED, send the critic's feedback back to "
             "the writer to revise, then to the critic again; repeat until the critic replies "
             "APPROVED, then END with the final couplet. Do not end before APPROVED.",
    ),
    # 0.2.5 gate → leader-driven LOOP with a CODED verdict-reading leader (terminates on APPROVED).
    "loop_raw": dict(
        op="curriculum_loop_raw",
        build=lambda: algebra.seq(AgentRef("writer"), AgentRef("critic")),
        leader_fn=make_loop_leader,
        teammates={
            "writer": "You are a writer. Write a two-line rhyming couplet, each line six-to-ten "
                      "words. If given critic feedback, revise. Output only the two lines.",
            "critic": "You are a critic. Given a two-line couplet, reply APPROVED if the lines rhyme "
                      "and each is six-to-ten words, else REJECTED + what to fix. Start with APPROVED "
                      "or REJECTED.",
        },
        task="Write a two-line rhyming couplet, each line six-to-ten words.",
    ),
    # 0.2.3 choice → leader-driven BRANCH. choice() does NOT compile to edges (branching is the
    # leader's job). Both specialists are members (par → both dispatchable); the leader routes to the
    # ONE that fits the request, then ends. Proves: leader-driven routing (item #4 branch).
    "branch": dict(
        op="curriculum_branch",
        build=lambda: algebra.par(AgentRef("coder"), AgentRef("writer")),
        teammates={
            "coder": "You are a software engineer. You only get sent CODE tasks. Give a concrete "
                     "1-2 sentence fix approach for the bug described.",
            "writer": "You are a marketing copywriter. You only get sent COPY tasks. If you were sent "
                      "a code/bug task by mistake, reply 'WRONG SPECIALIST'.",
        },
        task="Route this request to the RIGHT specialist and dispatch ONLY that one (not both), then "
             "END: request = 'fix the NullPointerException in auth.py login handler'. Members: coder "
             "(handles code/bugs), writer (handles marketing copy). Pick the correct one.",
    ),
}


def run_node(key):
    spec = TOPOLOGIES[key]
    team_dir = os.path.join(RUNROOT, key)
    os.system(f"rm -rf {team_dir}")

    Klass = type("T", (Team,), {"op": spec["op"], "build": lambda self: spec["build"]()})
    teammates = {n: mk(n, sp) for n, sp in spec["teammates"].items()}
    leader_rt = MiniMaxRuntime("leader", tools=[],
                               system_prompt="You are the team leader. Follow the instructions in "
                                             "each prompt exactly and reply with ONE JSON object only.")

    log(f"NODE {key}: running LEADER-DRIVEN with an automated LLM leader (llm_leader) …")
    res = run_team(Klass({}), spec["task"], llm_leader(leader_rt), teammates, team_dir,
                   max_steps=16, max_fixes=3)

    # ── read what ACTUALLY happened, from the files ──
    report = {"node": key, "ok": res["ok"], "report": res.get("report", ""),
              "error": res.get("error", ""), "team_dir": team_dir}
    msgs = res["messages"]
    report["responders_in_order"] = [m["frm"] for m in msgs if m["kind"] == "response"]
    report["dispatches"] = [(m["frm"], m["to"]) for m in msgs if m["kind"] == "dispatch"]
    report["blocks"] = [t["blocked"] for t in res["transcript"] if "blocked" in t]
    # concurrency evidence: the ordered stream of dispatched / finished(+still_running) events
    evs = []
    for t in res["transcript"]:
        if "dispatched" in t:
            evs.append(f"dispatch→{t['dispatched']}")
        elif "finished" in t:
            evs.append(f"finished={t['finished']} still_running={t['alert'].get('still_running')}")
        elif "cancelled" in t:
            evs.append(f"cancelled={t['cancelled']}")
    report["concurrency_stream"] = evs

    # the actual artifact contents (what each teammate produced) — read from disk
    art = os.path.join(team_dir, "sessions", "session", "artifacts")
    report["artifacts"] = {}
    if os.path.isdir(art):
        for f in sorted(os.listdir(art)):
            report["artifacts"][f] = open(os.path.join(art, f)).read()[:600]
    return report


def show(r):
    print("\n" + "=" * 78)
    print(f"NODE: {r['node']}   ok={r['ok']}   report={r['report']!r}")
    if r["error"]:
        print(f"  ERROR: {r['error']}")
    print(f"  dispatches (leader→teammate): {r['dispatches']}")
    print(f"  responders in GUARDRAIL-ENFORCED order: {r['responders_in_order']}")
    if r["blocks"]:
        print("  GUARDRAIL BLOCKS the LLM leader hit (the state machine working):")
        for b in r["blocks"]:
            print(f"    - {b}")
    else:
        print("  (no guardrail blocks — the LLM leader proposed a valid order first try)")
    if r.get("concurrency_stream"):
        print("  EXECUTION STREAM (dispatch / finish + who's still running):")
        for e in r["concurrency_stream"]:
            print(f"    → {e}")
    print("  ARTIFACTS the teammates actually wrote:")
    for f, c in r["artifacts"].items():
        print(f"    · {f}:\n        {c.strip()[:400]}")
    print("=" * 78)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None)
    args = ap.parse_args()
    keys = [args.only] if args.only else list(TOPOLOGIES)
    results = []
    for k in keys:
        try:
            results.append(run_node(k))
        except Exception as e:
            import traceback; traceback.print_exc()
            results.append({"node": k, "ok": False, "error": f"{type(e).__name__}: {e}",
                            "dispatches": [], "responders_in_order": [], "blocks": [], "artifacts": {},
                            "report": ""})
    for r in results:
        show(r)
    json.dump(results, open(os.path.join(SD, "learner_results.json"), "w"), indent=2)
    log(f"wrote learner_results.json ({len(results)} node(s))")
    sys.stdout.flush()
    os._exit(0)   # heaven non-daemon threads → hard exit
