"""
agentdir.py — THE DEVDIR AS A CLASS: an agent's directory-body, first-class.

The missing half of the WoS port (found 2026-08-08): cave-teams ported WoS's
ECONOMY (skillcraft.py, execute.sh verb-for-verb) but not its OPERATING
ENVIRONMENT — the agent template (`agents/_template/`: CLAUDE.md identity +
the .claude/skills loadout: execute_in_game, test_skill, skill_types, places,
bug_report, meta-PE…) and the embodiment (a session RUNS IN the dir). Those
lived on as hand glue because the library had no type for them — and what has
no constructor in the target is invisible to a port. This class is that type:

    AgentDir.from_template(root, name)   → build the BODY (the vendored WoS
                                           template, {{AGENT_ID}} rendered —
                                           the original instantiation rule)
    .equip_skill / .equip_rule           → the .claude loadout, claude-native
    .embody(runtime)                     → THE SOCKET: bind a runtime to the
                                           dir (sets cwd/working_dir/agent_dir
                                           on runtimes that carry them —
                                           heaven's claude_parity hook then
                                           picks up .claude on tool use;
                                           Claude Code runs there natively)
    .crafted() / .bought() / .tests()    → harvest what the agent made
    .rehydrate(runtime)                  → embody an EXISTING body (the dir IS
                                           the identity; give it to a fresh
                                           process and that process is the
                                           agent)

The vendored template is the REAL one (world-of-skillcraft/agents/_template,
copied verbatim into cave_teams/wos_template/). Worlds stay dir-agnostic;
AgentDir is the seam between the runtime library and the folder world.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_TEMPLATE = Path(__file__).resolve().parent / "wos_template"

# runtime attributes the embodiment socket knows how to set, in order
_DIR_ATTRS = ("cwd", "working_dir", "agent_dir")


class AgentDir:
    """An agent's body. The dir is the identity: CLAUDE.md (who), .claude/
    (the loadout), crafted/ (what it makes), bought/ (what it acquired)."""

    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name

    # ── build ────────────────────────────────────────────────────────────────
    @classmethod
    def from_template(cls, root, name: str,
                      template=None) -> "AgentDir":
        """Stamp a body from the template (default: the vendored WoS
        `agents/_template`), rendering `{{AGENT_ID}}` → name in every .md —
        the original repo's instantiation rule."""
        template = Path(template or DEFAULT_TEMPLATE)
        if not template.is_dir():
            raise FileNotFoundError(f"agent template not found: {template}")
        dest = Path(root) / name
        if dest.exists():
            raise FileExistsError(f"agent body already exists: {dest}")
        shutil.copytree(template, dest)
        for md in dest.rglob("*.md"):
            text = md.read_text(encoding="utf-8")
            if "{{AGENT_ID}}" in text:
                md.write_text(text.replace("{{AGENT_ID}}", name),
                              encoding="utf-8")
        (dest / "crafted").mkdir(exist_ok=True)
        (dest / "bought").mkdir(exist_ok=True)
        return cls(dest)

    @classmethod
    def existing(cls, path) -> "AgentDir":
        """Wrap an existing body (no scaffolding — the dir IS the agent)."""
        p = Path(path)
        if not p.is_dir():
            raise FileNotFoundError(f"no agent body at {p}")
        return cls(p)

    # ── the loadout (claude-native) ──────────────────────────────────────────
    def equip_skill(self, name: str, content: str) -> Path:
        d = self.path / ".claude" / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        p = d / "SKILL.md"
        p.write_text(content, encoding="utf-8")
        return p

    def equip_rule(self, name: str, content: str) -> Path:
        d = self.path / ".claude" / "rules"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{name}.md"
        p.write_text(content, encoding="utf-8")
        return p

    def skills(self) -> List[str]:
        d = self.path / ".claude" / "skills"
        return sorted(x.name for x in d.iterdir() if x.is_dir()) \
            if d.is_dir() else []

    def identity(self) -> str:
        p = self.path / "CLAUDE.md"
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    # ── embodiment (THE SOCKET) ──────────────────────────────────────────────
    def embody(self, runtime: Any) -> Any:
        """Bind a runtime to this body. Sets every dir-attribute the runtime
        carries (cwd / working_dir / agent_dir) and always attaches
        `agent_dir` so prompt-building code can reference the body. The
        runtime's own machinery does the rest (heaven: claude_parity injects
        .claude rules+CLAUDE.md on tool use; Claude Code: runs in the dir).
        Returns the runtime (chainable)."""
        for attr in _DIR_ATTRS:
            if hasattr(runtime, attr):
                setattr(runtime, attr, str(self.path))
        if not hasattr(runtime, "agent_dir"):
            try:
                runtime.agent_dir = str(self.path)
            except Exception:
                pass                       # frozen runtimes: path via prompts
        return runtime

    def rehydrate(self, runtime: Any) -> Any:
        """Alias of embody for an existing body: give the dir to a fresh
        process and that process IS the agent."""
        return self.embody(runtime)

    # ── harvest (what the agent made / acquired) ─────────────────────────────
    def crafted(self) -> List[Path]:
        d = self.path / "crafted"
        return sorted(p for p in d.glob("*.md")) if d.is_dir() else []

    def bought(self) -> Dict[str, List[Path]]:
        d = self.path / "bought"
        return {seller.name: sorted(seller.glob("*.md"))
                for seller in d.iterdir() if seller.is_dir()} \
            if d.is_dir() else {}

    def tests(self) -> List[dict]:
        d = self.path / "crafted" / ".tests"
        out = []
        if d.is_dir():
            for p in sorted(d.glob("*.json")):
                try:
                    out.append(json.loads(p.read_text()))
                except ValueError:
                    pass
        return out

    def __repr__(self):
        return f"AgentDir({self.path})"


def scaffold_agents(root, names: List[str],
                    template=None) -> Dict[str, AgentDir]:
    """Stamp a roster of bodies — the world-boot helper (what every app has
    been hand-writing as `_seed_world` glue)."""
    return {n: AgentDir.from_template(root, n, template=template)
            for n in names}


__all__ = ["AgentDir", "scaffold_agents", "DEFAULT_TEMPLATE"]
