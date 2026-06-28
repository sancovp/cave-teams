"""
Three primitives for agent execution.

1. run_opus — claude -p with Opus 4.6 1M
2. continue_opus — resume prior claude -p session
3. run_minimax — MiniMax-M2.7-highspeed via Anthropic-compatible API
"""

import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Result from any primitive execution."""
    text: str = ""
    session_id: Optional[str] = None
    transcript_path: Optional[str] = None
    duration_ms: int = 0
    error: Optional[str] = None
    success: bool = True


def _claude_env() -> dict:
    """Subprocess env with ANTHROPIC_API_KEY stripped so claude -p uses subscription auth."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def _parse_claude_stream(stdout: str, transcript_dir: Optional[str] = None) -> dict:
    """Parse claude -p stream-json output. Returns {text, session_id, transcript_path}."""
    text_parts = []
    session_id = None
    events = []

    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            events.append(event)

            etype = event.get("type", "")

            if etype == "system" and event.get("subtype") == "init":
                session_id = event.get("session_id") or session_id

            elif etype == "assistant":
                for block in event.get("message", {}).get("content", []):
                    if block.get("type") == "text":
                        text_parts.append(block["text"])

            elif etype == "content_block_delta":
                delta = event.get("delta", {})
                if delta.get("type") == "text_delta":
                    text_parts.append(delta.get("text", ""))

            elif etype == "result" and event.get("is_error"):
                text_parts.append(event.get("result", ""))

        except json.JSONDecodeError:
            text_parts.append(line)

    transcript_path = None
    if transcript_dir:
        Path(transcript_dir).mkdir(parents=True, exist_ok=True)
        transcript_path = str(Path(transcript_dir) / f"{int(time.time())}.jsonl")
        with open(transcript_path, "w") as f:
            for event in events:
                f.write(json.dumps(event) + "\n")

    return {"text": "".join(text_parts), "session_id": session_id, "transcript_path": transcript_path}


def _run_claude_p(cmd: list, prompt: str, cwd: str, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run claude -p subprocess with subscription auth."""
    return subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                          cwd=cwd, timeout=timeout, env=_claude_env())


def _stream_claude_p(cmd: list, prompt: str, cwd: str,
                     on_chunk: Callable[[str], None],
                     transcript_dir: Optional[str] = None,
                     timeout: int = 600) -> dict:
    """Popen claude -p and stream stdout NDJSON LIVE — fire on_chunk(text) per text_delta
    as tokens arrive (token-level streaming, vs _run_claude_p's run-then-parse). Returns
    {text, session_id, transcript_path}. Caller must pass --include-partial-messages so the
    CLI emits content_block_delta events."""
    proc = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, cwd=cwd, env=_claude_env(),
    )
    try:
        proc.stdin.write(prompt)
        proc.stdin.close()
    except Exception:
        pass

    text_parts: List[str] = []
    session_id = None
    events = []
    for line in proc.stdout:                       # blocks per line as the CLI emits it
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        events.append(event)
        etype = event.get("type", "")
        if etype == "system" and event.get("subtype") == "init":
            session_id = event.get("session_id") or session_id
        elif etype == "content_block_delta":
            d = event.get("delta", {})
            if d.get("type") == "text_delta":
                t = d.get("text", "")
                if t:
                    text_parts.append(t)
                    try:
                        on_chunk(t)
                    except Exception:
                        pass
        elif etype == "assistant" and not text_parts:
            # partial messages off (or no deltas seen): fall back to the whole assistant text
            for b in event.get("message", {}).get("content", []):
                if b.get("type") == "text" and b.get("text"):
                    text_parts.append(b["text"])
                    try:
                        on_chunk(b["text"])
                    except Exception:
                        pass
        elif etype == "result" and event.get("is_error"):
            text_parts.append(event.get("result", ""))
    try:
        proc.wait(timeout=timeout)
    except Exception:
        proc.kill()

    transcript_path = None
    if transcript_dir:
        Path(transcript_dir).mkdir(parents=True, exist_ok=True)
        transcript_path = str(Path(transcript_dir) / f"{int(time.time())}.jsonl")
        with open(transcript_path, "w") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")

    return {"text": "".join(text_parts), "session_id": session_id, "transcript_path": transcript_path}


def run_opus(
    system_prompt: str,
    prompt: str,
    cwd: str = ".",
    mcp_config: Optional[str] = None,
    max_turns: int = 50,
    transcript_dir: Optional[str] = None,
    model: str = "claude-opus-4-6[1m]",
    on_chunk: Optional[Callable[[str], None]] = None,
) -> AgentResult:
    """Run a single claude -p call. Model defaults to Opus but accepts Sonnet.

    If on_chunk is given, streams token deltas live via on_chunk(text) (Popen +
    --include-partial-messages); otherwise uses the run-then-parse path."""
    start = time.time()

    cmd = [
        "claude", "-p",
        "--model", model,
        "--system-prompt", system_prompt,
        "--permission-mode", "bypassPermissions",
        "--output-format", "stream-json",
        "--max-turns", str(max_turns),
    ]
    if mcp_config:
        cmd += ["--mcp-config", mcp_config]

    try:
        if on_chunk is not None:
            cmd += ["--include-partial-messages"]
            parsed = _stream_claude_p(cmd, prompt, cwd, on_chunk, transcript_dir)
        else:
            proc = _run_claude_p(cmd, prompt, cwd)
            parsed = _parse_claude_stream(proc.stdout, transcript_dir)
    except subprocess.TimeoutExpired:
        return AgentResult(error="timeout after 600s", success=False)
    except Exception as e:
        logger.error("run_opus failed: %s", e, exc_info=True)
        return AgentResult(error=str(e), success=False)

    duration_ms = int((time.time() - start) * 1000)

    return AgentResult(
        text=parsed["text"],
        session_id=parsed["session_id"],
        transcript_path=parsed["transcript_path"],
        duration_ms=duration_ms,
    )


def continue_opus(
    session_id: str,
    prompt: str,
    cwd: str = ".",
    transcript_dir: Optional[str] = None,
    model: str = "claude-sonnet-4-6",
    on_chunk: Optional[Callable[[str], None]] = None,
) -> AgentResult:
    """Continue a prior claude -p conversation. Streams via on_chunk if given."""
    start = time.time()

    cmd = [
        "claude", "-p",
        "-r", session_id,
        "--model", model,
        "--permission-mode", "bypassPermissions",
        "--output-format", "stream-json",
    ]

    try:
        if on_chunk is not None:
            cmd += ["--include-partial-messages"]
            parsed = _stream_claude_p(cmd, prompt, cwd, on_chunk, transcript_dir)
        else:
            proc = _run_claude_p(cmd, prompt, cwd)
            parsed = _parse_claude_stream(proc.stdout, transcript_dir)
    except subprocess.TimeoutExpired:
        return AgentResult(error="timeout after 600s", success=False)
    except Exception as e:
        logger.error("continue_opus failed: %s", e, exc_info=True)
        return AgentResult(error=str(e), success=False)

    duration_ms = int((time.time() - start) * 1000)

    return AgentResult(
        text=parsed["text"],
        session_id=parsed.get("session_id") or session_id,
        transcript_path=parsed["transcript_path"],
        duration_ms=duration_ms,
    )


def run_minimax(
    system_prompt: str,
    prompt: str,
    model: str = "MiniMax-M2.7-highspeed",
    max_tokens: int = 8192,
    on_chunk: Optional[Callable[[str], None]] = None,
) -> AgentResult:
    """Run MiniMax via Anthropic-compatible API. Streams via on_chunk if given."""
    start = time.time()

    try:
        from anthropic import Anthropic
    except ImportError:
        return AgentResult(error="anthropic package not installed", success=False)

    api_key = os.environ.get("MINIMAX_API_KEY")
    if not api_key:
        return AgentResult(error="MINIMAX_API_KEY not set", success=False)

    try:
        client = Anthropic(api_key=api_key, base_url="https://api.minimax.io/anthropic")
        if on_chunk is not None:
            text = ""
            with client.messages.stream(
                model=model, system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            ) as stream:
                for delta in stream.text_stream:
                    text += delta
                    try:
                        on_chunk(delta)
                    except Exception:
                        pass
        else:
            response = client.messages.create(
                model=model, system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
            )
            text = ""
            for block in (response.content or []):
                if hasattr(block, "text") and block.type == "text":
                    text = block.text
                    break
    except Exception as e:
        logger.error("run_minimax failed: %s", e, exc_info=True)
        return AgentResult(error=str(e), success=False, duration_ms=int((time.time() - start) * 1000))

    return AgentResult(text=text, duration_ms=int((time.time() - start) * 1000))


@dataclass
class ImageResult:
    path: str = ""
    duration_ms: int = 0
    error: Optional[str] = None
    success: bool = True


def generate_image(
    prompt: str,
    output_path: str = "",
    model: str = "gpt-image-2",
    size: str = "1024x1024",
    quality: str = "low",
) -> ImageResult:
    """Generate an image via OpenAI gpt-image-2. Returns path to saved PNG."""
    import base64
    start = time.time()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return ImageResult(error="OPENAI_API_KEY not set", success=False)

    if not output_path:
        output_path = f"/tmp/cave-teams/images/{int(time.time())}.png"

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        result = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality=quality,
        )
        image_b64 = result.data[0].b64_json
        image_bytes = base64.b64decode(image_b64)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(image_bytes)

        duration_ms = int((time.time() - start) * 1000)
        logger.info("Image generated: %s (%dms, %d bytes)", output_path, duration_ms, len(image_bytes))
        return ImageResult(path=output_path, duration_ms=duration_ms)

    except Exception as e:
        logger.error("generate_image failed: %s", e, exc_info=True)
        return ImageResult(error=str(e), success=False,
                          duration_ms=int((time.time() - start) * 1000))
