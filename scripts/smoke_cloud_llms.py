"""Live smoke test for the cloud LLM adapters.

Reads ``.env`` from the repo root (no python-dotenv dep — we parse it
ourselves), then sends one short Vietnamese prompt through each
configured provider and prints the result. Skips any provider whose
API key is not set, so you can fill in just one and try it.

Usage::

    python scripts/smoke_cloud_llms.py

    # or pass providers explicitly:
    python scripts/smoke_cloud_llms.py openai anthropic ollama

The script is intentionally NOT a pytest — it makes real network
calls and costs cents per run. Tests with mocked HTTP live in
``tests/test_llm.py``.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENV_FILE = REPO / ".env"

PROMPT = "Trả lời ngắn gọn (một câu): Thủ đô của Việt Nam là gì?"


def _load_dotenv(path: Path) -> None:
    """Tiny KEY=VALUE parser. Skips comments and blank lines."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v and k not in os.environ:
            os.environ[k] = v


def _try(label: str, fn) -> None:  # type: ignore[no-untyped-def]
    print(f"\n=== {label} ===")
    t = time.perf_counter()
    try:
        out = fn()
        dt = time.perf_counter() - t
        print(f"  {out!r}")
        print(f"  ({dt:.2f}s)")
    except Exception as exc:
        print(f"  SKIP/ERROR: {type(exc).__name__}: {exc}")


def main() -> int:
    _load_dotenv(ENV_FILE)
    targets = sys.argv[1:] or ["openai", "anthropic", "ollama"]

    if "openai" in targets:
        if os.environ.get("OPENAI_API_KEY"):
            from nom.llm import OpenAI

            _try("OpenAI (gpt-4o-mini)", lambda: OpenAI().complete(PROMPT))
        else:
            print("\n=== OpenAI ===\n  SKIP: OPENAI_API_KEY not set in .env")

    if "anthropic" in targets:
        if os.environ.get("ANTHROPIC_API_KEY"):
            from nom.llm import Anthropic

            _try("Anthropic (claude-haiku-4-5)", lambda: Anthropic().complete(PROMPT))
        else:
            print("\n=== Anthropic ===\n  SKIP: ANTHROPIC_API_KEY not set in .env")

    if "ollama" in targets:
        from nom.llm import Ollama

        _try("Ollama (qwen3:1.7b)", lambda: Ollama(model="qwen3:1.7b").complete(PROMPT))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
