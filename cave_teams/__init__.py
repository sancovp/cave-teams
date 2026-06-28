"""
CAVE Teams — Programmable agent teams with persistent conversations.

Core:
    Conversation      — Persistent agent conversation (remembers everything)
    Harness           — File watcher that delivers messages between agents
    TeamLeader        — Opus/MiniMax leader that orchestrates by reasoning

Primitives:
    run_opus()        — Single claude -p call with Opus 4.6 1M
    continue_opus()   — Continue a prior claude -p conversation
    run_minimax()     — Direct MiniMax call

Seam + frontend + adaptor (the 2026-06 build — events OUT, decoupled frontend):
    EventBus, TeamEvent   — the on_event seam every Harness now emits through
    TeamGalleryServer     — the live web gallery (/ws + /emit + page)
    FrontendListener / HttpFrontendListener — push a team's events to the gallery
    build_team / spawn_team — the CAVE adaptor: spin up a team on the fly, wired live

Legacy (stateless, being replaced):
    Team, TeamAgent   — Old stateless orchestrator
"""

from .primitives import run_opus, continue_opus, run_minimax, generate_image, AgentResult, ImageResult
from .conversation import Conversation
from .events import EventBus, TeamEvent, FileListener, CallbackListener
from .harness import Harness, Condition
from .conditions import (
    when_flag, when_not_flag, after, when, all_of, any_of, wrap_cave_automation,
)
# the REAL chain ontology (vendored from SDNA — pure stdlib) + the typed Dovetail data-plane +
# cave-teams' ConcurrentChain. cave-teams is chain-ontology NATIVE: every agent type is a Link.
from .chain_ontology import (
    Link, LinkResult, LinkStatus, Chain, EvalChain, Compiler, ConfigLink, LinkConfig,
)
from .concurrent import ConcurrentChain
from .dovetail import DovetailModel, HermesConfigInput
from .links import AgentLink
# A MiniMax agent via the heaven framework (the onionmorph/Conductor path — self-auths, no env key).
# heaven_base/cave are imported lazily inside execute(), so this import is host-safe (zero heaven dep).
from .heaven_minimax import HeavenMiniMaxLink, build_minimax_config, minimax_coords
# The metacontrol function: ONE super-compiled top that can drive the whole native API from a
# data spec, in any sequence. NOT how you program (use the native API for that) — the universal
# driver over it, extensible via register() (canonical/goldenized ops). See cave.py.
from .cave import (
    cave, golden, register, register_fn, registered_ops, registered_fns,
    scan_caves, scan_library, _build as build_from_spec,
)
from . import topologies
from .topologies import (
    pipeline, chain, fan_out, broadcast, synthesis_gate, map_reduce, tournament,
    eval_chain, loop_refine, duo, round_robin, Router, router, chain_from_spec,
)
# a team AS an agent (homoiconic: agent = team = agent = Link) → runtime stacking + override-run
from .runtime import TeamRuntime, as_agent
# Phase 2: the SDNA/heaven agent zoo as leaf Links (as_link adapts any runnable; SDNAC is already a Link)
from .sdna_bridge import as_link, RunnableLink, SDNA_AVAILABLE
from .chain_ontology import CHAIN_ONTOLOGY_SOURCE
# Phase 3: the agent-composition ALGEBRA over Links (laws in LAWS.md, verified in test_algebra_laws.py)
from . import algebra
from .algebra import seq, par, choice, gate, dovetail, skip, team, lift, Skip, Subgraph
# Phase 4: literal algebra NOTATION (a >> b, a | b, >> dove(D) >>) — installs >>/| on Link
from . import dsl
from .dsl import dove
# Team topology: the general partial-order scheduler (blockedBy DAG) — seq/par are its limits
from .dag import dag, DagChain
# Team topology: the arena / stigmergy blackboard (the gameworld core) — N agents ↔ shared state ↔ deity
from .blackboard import blackboard, Blackboard
# The genetic operator: copy a winner's dir (its AIOS) + wipe session memory → next generation
from .evolve import evolve, evolve_dir, select_winners
# The Economic Crafter Sim: compete → user-buys → select → evolve over generations (compiler + lab)
from .sim import crafter_sim
# The bounded epoch: carry / reset / ratchet boundary (the WoS season — the standard climbs)
from .season import season, Season, carry_reset_ratchet
# A WHOLE gameworld as one composable object: a program, and a class (instantiable / from_spec / subclassable)
from .gameworld import GameWorld, world_as_agent
# Workflow-tool parity: pipeline (no-barrier streaming), parallel (capped), run_until, content-hash
# resume (Memo), schema-output (with_schema). `pipeline` stays module-qualified (cave_teams.workflow.pipeline)
# to avoid clashing with topologies.pipeline (the sequential Chain builder).
from . import workflow
from .workflow import parallel, run_until, Memo, content_key, with_schema, SchemaError
# NPCs: agents in the world callable by players via a skill (an NPC can be a whole GameWorld)
from .npc import npc_mutator
# Context surgery (inject / weave / dovetail) — the context-assembly plane (native + sdna re-export)
from . import context_engineering
from .context_engineering import compose_context, weave_text, inject_context, weave_context, CONTEXT_ENGINEERING_SOURCE
# Metacog shell (a SEPARATE meta-pattern): executor→observer→meta[STATIC]→skill_editor, compounds
from .metacog import metacog_shell, MetacogShell
from .leader import TeamLeader
from .orchestrator import Team, TeamAgent, AgentBackend, Task
from .jobworld import JobworldTeam
from .adaptor import build_team, spawn_team

# Frontend imports fastapi/uvicorn lazily — keep them optional so the core library
# (agents + seam + adaptor) imports cleanly even where the web deps aren't installed.
try:
    from .frontend import TeamGalleryServer, FrontendListener, HttpFrontendListener
except Exception:  # pragma: no cover
    pass
