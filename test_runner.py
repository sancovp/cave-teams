"""Test the LEADER-DRIVEN runner + the guardrail check-and-reprompt loop (rule 01).
Pure stdlib + algebra; no cave. A scripted leader deliberately messages a teammate too early."""
import tempfile

from cave_teams.team import Team
from cave_teams.wiring import AgentRef
from cave_teams.algebra import seq
from cave_teams.runner import run_team, Proposal


class Pipe(Team):
    op = "pipe_demo"

    def build(self):
        return seq(AgentRef("a"), AgentRef("b"))


def test_guardrail_blocks_then_leader_self_corrects():
    team = Pipe({})
    # scripted leader: first messages b (INVALID — a must go first), then fixes to a, then b, then END
    script = iter([
        Proposal(to="b", prompt="go b"),          # invalid: not b's turn
        Proposal(to="a", prompt="read the task"),  # valid (a is ready)
        Proposal(to="b", prompt="read a's output"),  # valid (a has responded)
        Proposal(end=True, report="pipeline complete"),
    ])
    blocks = []

    def leader(ctx):
        if ctx.get("error"):
            blocks.append(ctx["error"])      # the guardrail re-prompted us with {e}
        return next(script)

    teammates = {"a": lambda p: "A's result", "b": lambda p: "B's result"}
    with tempfile.TemporaryDirectory() as td:
        res = run_team(team, "do the thing", leader, teammates, td + "/team")

    assert res["ok"], res
    assert res["report"] == "pipeline complete", res
    # the early 'b' was blocked and the leader was re-prompted with the turn-order error
    assert blocks and "isn't b's turn" in blocks[0], blocks
    # teammates ran in the guardrail-enforced order
    responders = [m["frm"] for m in res["messages"] if m["kind"] == "response"]
    assert responders == ["a", "b"], responders
    print("ok  leader messaged b too early -> BLOCKED + reprompted -> self-fixed to a -> b -> END")
    print("    guardrail {e}:", blocks[0])
    print("    run order:", responders, "| report:", res["report"])


def test_unknown_agent_blocked():
    team = Pipe({})
    script = iter([Proposal(to="zeb", prompt="hi"), Proposal(end=True, report="ok")])
    seen = []

    def leader(ctx):
        if ctx.get("error"):
            seen.append(ctx["error"])
        return next(script)

    with tempfile.TemporaryDirectory() as td:
        res = run_team(team, "t", leader, {"a": lambda p: "x", "b": lambda p: "y"}, td + "/t")
    assert res["ok"], res
    assert seen and "is not in this team" in seen[0], seen
    print("ok  leader messaged a non-member -> blocked:", seen[0])


def test_finish_report_carries_path_and_open_rules():
    from cave_teams.runner import run_team
    team = Pipe({})
    alerts = []
    script = iter([
        Proposal(to="a", prompt="read the task"),
        Proposal(to="b", prompt="read a's output"),
        Proposal(end=True, report="done"),
    ])

    def leader(ctx):
        if ctx.get("alert"):
            alerts.append(ctx["alert"])     # the teammate-finish report the leader receives
        return next(script)

    teammates = {"a": lambda p: "A's detailed research findings", "b": lambda p: "B's writeup"}
    open_rules = {"a": ["a's research must be accurate and complete before b writes"]}
    with tempfile.TemporaryDirectory() as td:
        res = run_team(team, "the topic", leader, teammates, td + "/team", open_rules=open_rules)

    assert res["ok"], res
    assert alerts, "leader never received a finish report"
    a_alert = alerts[0]
    assert a_alert["finished"] == "a"
    # the output is given as a PATH, never pasted in (pointer-not-payload)
    assert a_alert["message_path"], a_alert
    assert "A's detailed research" not in str(a_alert), "output must NOT be inlined into the report"
    # the OPEN-WORLD rules for that step are surfaced to the leader (not checked by cave-teams)
    assert a_alert["open_rules"] == ["a's research must be accurate and complete before b writes"]
    print("ok  finish-report: message PATH (not inlined) + open-world rules surfaced to the leader")
    print("    alert:", {k: a_alert[k] for k in ("finished", "message_path", "open_rules")})


if __name__ == "__main__":
    test_guardrail_blocks_then_leader_self_corrects()
    test_unknown_agent_blocked()
    test_finish_report_carries_path_and_open_rules()
    print("\nLEADER-DRIVEN RUNNER TESTS PASSED")
