"""
Persistent agent conversations — agents remember everything.

Each agent has a Conversation that maintains full message history.
MiniMax: history passed with every call. Opus: session_id for continuation.
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from typing import Callable

from .primitives import run_opus, continue_opus, AgentResult

logger = logging.getLogger(__name__)

# backends that route to the claude -p path (run_opus) vs the MiniMax API path
_CLAUDE_BACKENDS = ("opus", "claude-p", "claude", "claude_p")


@dataclass
class Message:
    role: str
    content: str
    ts: float = field(default_factory=time.time)
    agent: str = ""


class Conversation:
    """Persistent conversation for one agent. Remembers everything."""

    def __init__(self, name: str, system_prompt: str, backend: str = "minimax",
                 model: Optional[str] = None, cwd: str = ".",
                 mcp_config: Optional[str] = None):
        self.name = name
        self.system_prompt = system_prompt
        self.backend = backend
        self._claude = backend in _CLAUDE_BACKENDS
        self.model = model or ("claude-sonnet-4-6" if self._claude else "MiniMax-M2.7-highspeed")
        self.cwd = cwd
        self.mcp_config = mcp_config
        self.messages: List[dict] = []
        self.session_id: Optional[str] = None
        self.transcript_path: Optional[str] = None

    def send(self, content: str, from_agent: str = "harness",
             on_chunk: Optional[Callable[[str], None]] = None) -> AgentResult:
        """Send a message and get response. Full history maintained.

        on_chunk (optional) streams token deltas live as they arrive — the Harness
        wires this to bus.emit('stream', ...) so a frontend shows the agent typing.
        """
        self.messages.append({"role": "user", "content": content})

        if self._claude:
            result = self._send_opus(content, on_chunk)
        else:
            result = self._send_minimax(on_chunk)

        if result.success and result.text:
            self.messages.append({"role": "assistant", "content": result.text})

        return result

    def _send_opus(self, content: str, on_chunk=None) -> AgentResult:
        if self.session_id:
            result = continue_opus(self.session_id, content, cwd=self.cwd,
                                   model=self.model, on_chunk=on_chunk)
        else:
            result = run_opus(self.system_prompt, content, cwd=self.cwd,
                              mcp_config=self.mcp_config, model=self.model, on_chunk=on_chunk)
        if result.session_id:
            self.session_id = result.session_id
        return result

    def _send_minimax(self, on_chunk=None) -> AgentResult:
        start = time.time()
        try:
            from anthropic import Anthropic
        except ImportError:
            return AgentResult(error="anthropic not installed", success=False)

        api_key = os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            return AgentResult(error="MINIMAX_API_KEY not set", success=False)

        try:
            client = Anthropic(api_key=api_key, base_url="https://api.minimax.io/anthropic")
            if on_chunk is not None:
                text = ""
                with client.messages.stream(
                    model=self.model, system=self.system_prompt,
                    messages=self.messages, max_tokens=8192,
                ) as stream:
                    for delta in stream.text_stream:
                        text += delta
                        try:
                            on_chunk(delta)
                        except Exception:
                            pass
            else:
                response = client.messages.create(
                    model=self.model,
                    system=self.system_prompt,
                    messages=self.messages,
                    max_tokens=8192,
                )
                text = ""
                for block in (response.content or []):
                    if hasattr(block, "text") and block.type == "text":
                        text = block.text
                        break
            return AgentResult(text=text, duration_ms=int((time.time() - start) * 1000))
        except Exception as e:
            logger.error("MiniMax call failed for %s: %s", self.name, e, exc_info=True)
            return AgentResult(error=str(e), success=False,
                               duration_ms=int((time.time() - start) * 1000))

    def history_length(self) -> int:
        return len(self.messages)

    def save_history(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            for msg in self.messages:
                f.write(json.dumps(msg) + "\n")

    def load_history(self, path: Path):
        if path.exists():
            self.messages = []
            for line in path.read_text().splitlines():
                if line.strip():
                    self.messages.append(json.loads(line))
