"""Real-LLM unit (needs cave + heaven + MINIMAX_API_KEY): the MiniMaxRuntime set_runtime backend.
The full team path is in test_cave_team.py."""
import asyncio

from cave_teams.examples import MiniMaxRuntime


def test_runtime_direct():
    rt = MiniMaxRuntime("probe", tools=[],
                        system_prompt="Reply with EXACTLY one word: PONG. Nothing else.")
    out = asyncio.run(rt.run("ping"))
    print("DIRECT runtime ->", repr(out)[:200])
    assert out.strip(), "empty response from MiniMax"
    print("ok  MiniMaxRuntime.run returned real text")


if __name__ == "__main__":
    test_runtime_direct()
    print("\nMINIMAX RUNTIME SMOKE PASSED")
