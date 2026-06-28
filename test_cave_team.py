"""Full integration (needs cave + heaven + MINIMAX_API_KEY): cave_team makes an ephemeral cave
server; a real FILE-WRITING leader (with file tools) orchestrates real teammates through the
session/inbox structure + guardrail; then it tears down."""
import glob
import os
import tempfile

from cave_teams.team import Team
from cave_teams.wiring import AgentRef
from cave_teams.algebra import seq
from cave_teams.server import cave_team
from cave_teams.examples import MiniMaxRuntime


class Brief(Team):
    op = "brief"

    def build(self):
        return seq(AgentRef("researcher"), AgentRef("writer"))


def main():
    leader = MiniMaxRuntime("leader", tools=None, system_prompt=(  # tools=None → file tools
        "You are a decisive team leader. Dispatch teammates ONE at a time in a valid order, "
        "and END as soon as the writer has produced the final result."))
    teammates = {
        "researcher": MiniMaxRuntime("researcher", tools=[], system_prompt=(
            "Output exactly 3 concise factual bullet points on the topic.")),
        "writer": MiniMaxRuntime("writer", tools=[], system_prompt=(
            "Turn the provided research into ONE tight sentence.")),
    }
    with tempfile.TemporaryDirectory() as td:
        res = cave_team(Brief({}), agent_runtimes=teammates, leader_runtime=leader,
                        task="Topic: why octopuses are considered intelligent.",
                        open_rules={"researcher": ["research must be accurate before the writer uses it"]},
                        team_dir=td + "/team", serve=True, max_steps=8)

        print("ok:", res["ok"])
        print("report:", (res.get("report") or res.get("error") or "")[:280])
        responders = [m["frm"] for m in res["messages"] if m["kind"] == "response"]
        print("run order:", responders)
        sess = td + "/team/sessions/session"
        print("session dirs:", sorted(os.path.basename(p) for p in glob.glob(sess + "/*")))
        print("leader_outbox files:", [os.path.basename(p) for p in glob.glob(sess + "/leader_outbox/*")])
        print("teammate inboxes:", sorted(os.path.basename(p) for p in glob.glob(sess + "/inbox/*")))

        assert res["ok"], res
        ri = responders.index("researcher") if "researcher" in responders else -1
        wi = responders.index("writer") if "writer" in responders else -1
        assert ri >= 0 and wi >= 0 and ri < wi, f"researcher must precede writer: {responders}"
        assert os.path.isdir(sess + "/inbox/researcher"), "no researcher inbox (delivery)"
    print("\nFULL cave_team (file-leader + session/inbox + ephemeral cave server) PASSED")


if __name__ == "__main__":
    main()
