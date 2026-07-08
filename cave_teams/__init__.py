"""
CAVE Teams — programmable agent teams, on cave.

A cave-team MAKES a cave server (a headless CAVEHTTPServer) that instantiates cave's agents, runs
them, and serves a state-machine flow encoded as conditions on MESSAGES — files in a per-team
messages dir. You write the team with the algebra (or a Team subclass), pass cave's agents +
message conditions; cave-teams CHECKs the team dir continuously and LIFTs (dispatches a
"read {path}" pointer) only when conditions hold; cave runs the agents, and the server is torn down
when the team finishes. Depends on cave + chain-ontology only.

See .claude/rules/00-03 and THE-ONLY-SOURCE-OF-TRUTH.md for the full architecture.
"""

# ── the message-state-machine SPINE (rule 01) ─────────────────────────────────
from .messages import TeamMessage, TeamDir, DISPATCH, RESPONSE, FLAG, DONE
from .flow import (
    Condition, Edge,
    responded, after, when_flag, when_message, all_of, any_of, always,
    register_condition, get_condition, registered_conditions,
)

# ── composition: algebra → edges, the Team carrier (rule 03) ──────────────────
from .wiring import AgentRef, compile_to_edges
from .team import Team, register_team, get_team, registered_teams

# ── the FACTORY: make / run / teardown an ephemeral cave server (rule 02) ─────
from .server import cave_team, make_headless_cave, EphemeralTeamServer

# ── the LEADER-DRIVEN run: leader (intelligent dovetail) + guardrail check-and-reprompt (rule 01) ──
from .session import TeamSession
from .runner import (
    run_team, run_team_async, Proposal, check_proposal, llm_leader, file_leader,
)

# ── the chain-ontology substrate (uco → sdna re-export → vendored) ────────────
from .chain_ontology import (
    Link, LinkResult, LinkStatus, Chain, EvalChain, Compiler, ConfigLink, LinkConfig,
    CHAIN_ONTOLOGY_SOURCE,
)
from .concurrent import ConcurrentChain

# ── leaf Links: a single agent as a Link + the any-runnable adapter ────────────
from .links import AgentLink, input_from_context
from .sdna_bridge import RunnableLink, as_link

# ── the agent-composition ALGEBRA + topologies (what cave-teams MAKES) ────────
from . import algebra, topologies, dsl
from .algebra import seq, par, choice, gate, dovetail, skip, team, lift, Skip, Subgraph
from .dsl import dove
from .topologies import (
    pipeline, chain, fan_out, broadcast, synthesis_gate, map_reduce, tournament,
    eval_chain, loop_refine, duo, round_robin, Router, router, chain_from_spec,
)
from .dag import dag, DagChain
from .blackboard import blackboard, Blackboard
from .season import season, Season, carry_reset_ratchet
from .gameworld import GameWorld, world_as_agent
from .npc import npc_mutator
from .metacog import metacog_shell, MetacogShell
from .evolve import evolve, evolve_dir, select_winners
from .sim import crafter_sim

# ── the CONFIG face: spec → topology + the golden library + metacontrol ───────
from .cave import (
    cave, golden, register, register_fn, registered_ops, registered_fns,
    scan_caves, scan_library, set_persona_compiler, _build as build_from_spec,
)

# ── the typed dovetail data-plane (⋈ — the SDNA-agent tier) ───────────────────
from .dovetail import DovetailModel, HermesConfigInput

# ── workflow-parity utilities ─────────────────────────────────────────────────
from . import workflow
from .workflow import parallel, run_until, Memo, content_key, with_schema, SchemaError

# ── image generation (ported forward from the pre-rebuild primitives.py — the ONE piece of the
# old runtime nothing in the rebuild replaced; needs `pip install openai` + OPENAI_API_KEY) ────
from .primitives import generate_image, ImageResult

# NOTE (refactor, 2026-06-28): the old reimplemented runtime — primitives (claude -p / run_minimax),
# conversation, harness, events, leader, orchestrator, runtime, jobworld, adaptor, frontend, links —
# is SUPERSEDED by cave + the new spine and is no longer imported here. The files remain on disk
# (refactor, don't delete) until a confirmed cleanup. claude-p/minimax move to examples/ as cave
# agents + set_runtime backends.

try:  # single source of truth = pyproject; never a drifting literal
    from importlib.metadata import version as _pkg_version
    __version__ = _pkg_version("cave-teams")
except Exception:  # not installed (running from a checkout)
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "AgentLink", "input_from_context", "RunnableLink", "as_link",
    "TeamMessage", "TeamDir", "DISPATCH", "RESPONSE", "FLAG", "DONE",
    "Condition", "Edge", "responded", "after", "when_flag", "when_message",
    "all_of", "any_of", "always", "register_condition", "get_condition", "registered_conditions",
    "AgentRef", "compile_to_edges", "Team", "register_team", "get_team", "registered_teams",
    "cave_team", "make_headless_cave", "EphemeralTeamServer",
    "run_team", "run_team_async", "Proposal", "check_proposal", "llm_leader", "file_leader", "TeamSession",
    "Link", "LinkResult", "LinkStatus", "Chain", "EvalChain", "Compiler", "ConfigLink", "LinkConfig",
    "CHAIN_ONTOLOGY_SOURCE", "ConcurrentChain",
    "algebra", "topologies", "dsl", "seq", "par", "choice", "gate", "dovetail", "skip", "team",
    "lift", "Skip", "Subgraph", "dove", "pipeline", "chain", "fan_out", "broadcast",
    "synthesis_gate", "map_reduce", "tournament", "eval_chain", "loop_refine", "duo", "round_robin",
    "Router", "router", "chain_from_spec", "dag", "DagChain", "blackboard", "Blackboard",
    "season", "Season", "carry_reset_ratchet", "GameWorld", "world_as_agent", "npc_mutator",
    "metacog_shell", "MetacogShell", "evolve", "evolve_dir", "select_winners", "crafter_sim",
    "cave", "golden", "register", "register_fn", "registered_ops", "registered_fns",
    "scan_caves", "scan_library", "set_persona_compiler", "build_from_spec", "DovetailModel", "HermesConfigInput",
    "workflow", "parallel", "run_until", "Memo", "content_key", "with_schema", "SchemaError",
    "generate_image", "ImageResult",
]
