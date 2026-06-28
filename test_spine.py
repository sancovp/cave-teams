"""Substrate test: messages-as-files (TeamDir) + conditions over the message log + the registry.
The team RUN is leader-driven — see test_runner.py. Pure stdlib, no cave."""
import tempfile

from cave_teams.messages import TeamDir, TeamMessage, RESPONSE
from cave_teams.flow import after, responded, register_condition, get_condition, registered_conditions


def test_messages_roundtrip():
    with tempfile.TemporaryDirectory() as t:
        d = TeamDir(t)
        d.write(TeamMessage(frm="A", to="B", kind=RESPONSE, text="hi"))
        log = d.read_all()
        assert len(log) == 1 and log[0].frm == "A" and log[0].kind == RESPONSE
    print("ok  messages roundtrip (a message IS a file)")


def test_conditions_over_log():
    log = [TeamMessage(frm="A", to="x", kind=RESPONSE)]
    assert responded("A")(log) and not responded("B")(log)
    assert after("A")(log) and not after("A", "B")(log)
    print("ok  conditions over the message log (after / responded)")


def test_conditions_registry():
    register_condition("after_A", after("A"))
    assert get_condition("after_A")([TeamMessage(frm="A", to="x", kind=RESPONSE)]) is True
    assert "after_A" in registered_conditions()
    print("ok  conditions registry (cave-teams owns this)")


if __name__ == "__main__":
    test_messages_roundtrip()
    test_conditions_over_log()
    test_conditions_registry()
    print("\nSUBSTRATE TESTS PASSED")
