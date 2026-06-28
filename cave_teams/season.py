"""
season.py — the bounded epoch with a carry / reset / RATCHET boundary (the WoS season).

A season runs an arena (any Link — typically a blackboard) on the board, then at the boundary applies an
`advance` transition:
    RESET   the transient currencies/boards (gold→100, trade_board cleared)   — does not accumulate
    CARRY   the earned state (xp, reputation, races, zettels)                  — persists by default
    RATCHET the valuation standard (rarity_consensus tightens)                 — the gate gets stricter = the climb
then the next season runs against the tightened standard.

season(arena, advance, seasons=N) is the WORLD-epoch — it carries the SAME agents across the boundary.
It composes with evolve (the AGENT-reproduction, which makes NEW agents). Both are boundary operators; a
Season IS a Link, so it wraps a blackboard (season ∘ blackboard) and nests like anything else.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from .chain_ontology import Link, LinkResult, LinkStatus


class Season(Link):
    """Run `arena` for `seasons` epochs, applying `advance(board, season_num)` between them."""

    def __init__(self, arena: Link, advance: Optional[Callable[[Dict[str, Any], int], Dict[str, Any]]] = None,
                 seasons: int = 1, state_key: str = "board", name: str = "season"):
        self.arena = arena
        self.advance = advance
        self.seasons = seasons
        self.state_key = state_key
        self.name = name

    async def execute(self, context: Optional[Dict[str, Any]] = None, **kwargs):
        ctx0 = dict(context) if context else {}
        board = dict(ctx0.get(self.state_key, {}))
        history = []

        for s in range(self.seasons):
            inp = dict(ctx0)
            inp[self.state_key] = board
            inp["season"] = s + 1
            r = await self.arena.execute(inp)
            board = dict((r.context or {}).get(self.state_key, board))
            history.append({"season": s + 1, "board": dict(board)})
            if s < self.seasons - 1 and self.advance is not None:     # boundary transition (not after the last)
                board = dict(self.advance(board, s + 1))

        final = dict(ctx0)
        final[self.state_key] = board
        final["_seasons"] = history
        final["output"] = board
        return LinkResult(status=LinkStatus.SUCCESS, context=final)

    def describe(self, depth: int = 0) -> str:
        return "  " * depth + f'season "{self.name}" ×{self.seasons} ∘ ' + self.arena.describe(0).lstrip()


def season(arena: Link, advance: Optional[Callable[[Dict[str, Any], int], Dict[str, Any]]] = None,
           seasons: int = 1, state_key: str = "board", name: str = "season") -> Season:
    return Season(arena, advance, seasons=seasons, state_key=state_key, name=name)


def carry_reset_ratchet(reset_to: Optional[Dict[str, Any]] = None,
                        ratchet: Optional[Callable[[Dict[str, Any], int], Dict[str, Any]]] = None
                        ) -> Callable[[Dict[str, Any], int], Dict[str, Any]]:
    """Build a season-boundary `advance`: set each key in `reset_to` to its default (the TRANSIENT
    currencies; a callable default is invoked), keep everything else (the EARNED state), then apply
    `ratchet(board, season_num)` to tighten the valuation standard. Everything not named in reset_to
    carries by default — earned state is the default, reset is the exception."""
    def _advance(board: Dict[str, Any], n: int) -> Dict[str, Any]:
        b = dict(board)
        for k, v in (reset_to or {}).items():
            b[k] = v() if callable(v) else v
        if ratchet is not None:
            b = dict(ratchet(b, n))
        return b
    return _advance


__all__ = ["season", "Season", "carry_reset_ratchet"]
