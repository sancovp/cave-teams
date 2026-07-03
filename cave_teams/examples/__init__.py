"""cave_teams.examples — the EXAMPLE INSTANCE backends (claude-p / minimax).

These are `set_runtime` backends, NOT Links and NOT core: cave-teams runs ANY agent runtime;
minimax + claude-p are just the demo ("run claude-code teams without Claude Code Teams, with
minimax or claude, from Claude Code"). A backend is any object with `.run(str) -> str`.
"""
from .minimax_runtime import MiniMaxRuntime
from .claude_p_runtime import ClaudePRuntime

__all__ = ["MiniMaxRuntime", "ClaudePRuntime"]
