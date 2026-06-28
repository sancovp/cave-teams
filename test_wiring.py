"""Substrate test: the algebra compiles to message-flow EDGES — the GUARDRAILS. seq/par/team
become per-teammate run-conditions (whose turn it is). The RUN is leader-driven (test_runner.py).
Pure stdlib + the chain-ontology algebra; no cave."""
from cave_teams.messages import TeamMessage, RESPONSE
from cave_teams.wiring import AgentRef, compile_to_edges
from cave_teams.algebra import seq, par, team


def _resp(*names):
    return [TeamMessage(frm=n, to="x", kind=RESPONSE) for n in names]


def _holds(edge, log):
    return all(c(log) for c in edge.conditions)


def test_seq_par_compile():
    by = {e.to: e for e in compile_to_edges(
        seq(AgentRef("A"), par(AgentRef("B"), AgentRef("C")), AgentRef("D")))}
    assert set(by) == {"A", "B", "C", "D"}
    assert _holds(by["A"], [])                      # A ready immediately
    assert not _holds(by["B"], [])                  # B not until A responds
    assert _holds(by["B"], _resp("A"))              # B ready after A
    assert _holds(by["C"], _resp("A"))              # C ready after A (parallel with B)
    assert not _holds(by["D"], _resp("A", "B"))     # D needs BOTH B and C
    assert _holds(by["D"], _resp("A", "B", "C"))    # D ready after B and C
    print("ok  seq(A, par(B,C), D) -> guardrail conditions are the correct partial order")


def test_team_inlines():
    by = {e.to: e for e in compile_to_edges(
        seq(team(seq(AgentRef("A"), AgentRef("B")), name="sub"), AgentRef("C")))}
    assert set(by) == {"A", "B", "C"}
    assert _holds(by["A"], [])
    assert _holds(by["B"], _resp("A"))
    assert _holds(by["C"], _resp("A", "B"))         # C after the team's exit (B) — closure law
    print("ok  team(seq(A,B)) >> C inlines (closure law)")


if __name__ == "__main__":
    test_seq_par_compile()
    test_team_inlines()
    print("\nWIRING TESTS PASSED")
