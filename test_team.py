"""Test the Team carrier (rule 03): three faces (Class/Config/Link) + auto-register + subclassing.
Pure stdlib + algebra; no cave."""
from cave_teams.team import Team, get_team, registered_teams
from cave_teams.wiring import AgentRef
from cave_teams.algebra import seq


class Pipeline(Team):
    op = "pipeline_demo"

    def build(self):
        return seq(*[AgentRef(a) for a in self.agents["steps"]])


class Sub(Pipeline):          # subclass — extend via super().build()
    op = "pipeline_sub"

    def build(self):
        return seq(super().build(), AgentRef("Z"))


def test_three_faces_and_register():
    t = Pipeline({"steps": ["A", "B", "C"]})
    # CLASS -> CONFIG
    cfg = t.to_config()
    assert cfg["op"] == "pipeline_demo" and cfg["agents"]["steps"] == ["A", "B", "C"]
    # CONFIG -> CLASS
    assert Pipeline.from_config(cfg).agents == t.agents
    # auto-registered as a team op
    assert "pipeline_demo" in registered_teams() and get_team("pipeline_demo") is Pipeline
    # CLASS -> LINK -> edges
    assert [e.to for e in t.edges()] == ["A", "B", "C"]
    print("ok  Team three faces (Class/Config/Link) + auto-register")


def test_subclass_override():
    s = Sub({"steps": ["A", "B"]})
    assert [e.to for e in s.edges()] == ["A", "B", "Z"]
    assert "pipeline_sub" in registered_teams()
    print("ok  subclass override (super().build() then Z):", [e.to for e in s.edges()])


if __name__ == "__main__":
    test_three_faces_and_register()
    test_subclass_override()
    print("\nTEAM TESTS PASSED")
