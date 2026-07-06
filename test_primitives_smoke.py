"""Smoke test for cave_teams.primitives — generate_image's no-key path.

No network, no mocks beyond env manipulation: with OPENAI_API_KEY unset, generate_image() must
short-circuit before ever importing openai or touching the network, returning a failed ImageResult."""
import os

from cave_teams import generate_image, ImageResult


def test_generate_image_no_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = generate_image("a red circle on a white background")

    assert isinstance(result, ImageResult)
    assert result.success is False
    assert result.error == "OPENAI_API_KEY not set"
    assert result.path == ""


if __name__ == "__main__":
    os.environ.pop("OPENAI_API_KEY", None)
    r = generate_image("a red circle on a white background")
    assert r.success is False and r.error == "OPENAI_API_KEY not set", r
    print("ok  generate_image() fails closed with no OPENAI_API_KEY:", r)
