"""
team.py — the Team base class (rule 03): the three-faces carrier (Class · Link · Config).

A Team:
  - build()s a topology (a Link of AgentRefs composed via the algebra)         [CLASS -> LINK]
  - is itself a Link, so it is stackable as a teammate (the closure law)
  - to_config() / from_config() round-trips to JSON                            [CLASS <-> CONFIG]
  - __init_subclass__ auto-registers every subclass as a team op + cave() op   [CONFIG face]

Agents are CAVE's (referenced by name); cave-teams owns only the conditions + teams registries.
The runtime drives a team via `edges()` (compile_to_edges of build()), not by executing the Link
in-process.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .chain_ontology import Link
from .wiring import compile_to_edges
from .flow import Edge


# ── the teams registry (cave-teams owns this; teams reference cave agents + conditions by name) ──
_TEAMS: Dict[str, type] = {}


def register_team(name: str, cls: type) -> None:
    _TEAMS[name] = cls


def get_team(name: str) -> type:
    if name not in _TEAMS:
        raise KeyError(f"unknown team '{name}' — register it (subclass Team with op='{name}'); "
                       f"known: {list(_TEAMS)}")
    return _TEAMS[name]


def registered_teams() -> List[str]:
    return list(_TEAMS)


class Team(Link):
    """Base class for a named, subclassable topology. Override `build()`."""

    op: str = None  # the registry op-name / team name (set on subclasses)

    def __init__(self, agents: Dict[str, Any], conditions: Dict[str, Any] = None, **spec):
        self.agents = agents                 # {role: cave-agent-name | [names]}
        self.conditions = conditions or {}   # {edge/role: [condition names]} (optional overrides)
        self.spec = spec

    # CLASS -> LINK
    def build(self) -> Link:
        raise NotImplementedError("override build() to return a topology (a Link of AgentRefs)")

    def edges(self) -> List[Edge]:
        """The message-flow edges the CHECK/LIFT runtime executes (rule 01)."""
        return compile_to_edges(self.build())

    async def execute(self, context=None, **kwargs):   # nominal Link-ness; the runtime uses edges()
        return await self.build().execute(context)

    # CLASS <-> CONFIG
    def to_config(self) -> Dict[str, Any]:
        return {"op": self.op, "agents": self.agents, "conditions": self.conditions, **self.spec}

    @classmethod
    def from_config(cls, spec: Dict[str, Any]) -> "Team":
        spec = dict(spec)
        spec.pop("op", None)
        agents = spec.pop("agents", {})
        conditions = spec.pop("conditions", {})
        return cls(agents, conditions, **spec)

    # CONFIG face — auto-register every subclass
    def __init_subclass__(cls, **kw):
        super().__init_subclass__(**kw)
        if getattr(cls, "op", None):
            register_team(cls.op, cls)
            try:  # also make it callable through the cave() config registry (best-effort)
                from .cave import register
                register(cls.op, lambda s, c=cls: c.from_config(s).build())
            except Exception:
                pass
