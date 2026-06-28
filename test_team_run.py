"""Real leader-driven team run (needs cave + heaven + MINIMAX_API_KEY).
A live MiniMax LEADER orchestrates researcher -> writer through run_team — guardrail + open rules,
all real LLMs. This is the full system end-to-end."""
import tempfile

from cave_teams.team import Team
from cave_teams.wiring import AgentRef
from cave_teams.algebra import seq
from cave_teams.runner import run_team, llm_leader
from cave_teams.examples import MiniMaxRuntime


class Brief(Team):
    op = "brief_team"

    def build(self):
        return seq(AgentRef("researcher"), AgentRef("writer"))


def main():
    leader = MiniMaxRuntime("leader", tools=[], system_prompt=(
        "You are a decisive team leader. Dispatch teammates ONE at a time, in a valid order, "
        "and END as soon as the writer has produced the final result."))
    teammates = {
        "researcher": MiniMaxRuntime("researcher", tools=[], system_prompt=(
            "You research. Given a topic, output exactly 3 concise factual bullet points.")),
        "writer": MiniMaxRuntime("writer", tools=[], system_prompt=(
            "You write. Turn the provided research into ONE tight sentence.")),
    }
    open_rules = {"researcher": ["the research must be factually accurate before the writer uses it"]}

    with tempfile.TemporaryDirectory() as td:
        res = run_team(Brief({}), "Topic: why octopuses are considered intelligent.",
                       llm_leader(leader), teammates, td + "/team",
                       open_rules=open_rules, max_steps=8, max_fixes=3)

    print("ok:", res["ok"])
    print("report:", (res.get("report") or res.get("error") or "")[:400])
    print("--- transcript ---")
    for step in res["transcript"]:
        if "blocked" in step:
            print("  BLOCKED ->", step["blocked"][:90])
        elif "dispatched" in step:
            print("  dispatched ->", step["dispatched"])
    responders = [m["frm"] for m in res["messages"] if m["kind"] == "response"]
    print("  run order:", responders)

    assert res["ok"], res
    ri = responders.index("researcher") if "researcher" in responders else -1
    wi = responders.index("writer") if "writer" in responders else -1
    assert ri >= 0 and wi >= 0 and ri < wi, f"researcher must run before writer; got {responders}"
    print("\nREAL LEADER-DRIVEN TEAM RUN PASSED")


if __name__ == "__main__":
    main()
