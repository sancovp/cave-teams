"""
primitives.py — standalone utility primitives that don't belong to the message-state-machine spine.

generate_image / ImageResult — ported VERBATIM from the pre-rebuild cave_teams (the monorepo copy
at sanctuary-revolution-alpha/application/cave-teams, which forked before the 2026-06-28 leader-driven
rebuild [commit 5efad65] and kept this old-runtime file). The rest of that old primitives.py
(AgentResult / run_opus / continue_opus / run_minimax / the claude -p subprocess plumbing) is
SUPERSEDED by cave.py's headless CAVEHTTPServer + the runner/session spine and is intentionally
NOT ported here — only image generation, which nothing in the rebuild replaced.

openai is imported LAZILY (inside the function) — no hard dependency; only needed if you actually
call generate_image(). Needs `pip install openai` + OPENAI_API_KEY set in the environment.
"""

import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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
