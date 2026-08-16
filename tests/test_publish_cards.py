"""Guards on the generated Hugging Face model cards.

These publish scripts once hard-coded ``pipeline_tag: text-generation`` on
encoder-decoder models. The Hub then rendered a causal-LM snippet and
widget, and ``pipeline("text-generation", ...)`` rejects a seq2seq model and
returns the prompt unchanged, so the advertised usage corrected nothing on
every input. It shipped to seven published repos before a user reported it.

The Hub infers the correct tag from ``config.json``, so the field should
simply be absent.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

PUBLISH_SCRIPTS = (
    "training/diacritic/publish_hf.py",
    "training/spell_correction/publish_hf.py",
    "training/onnx_export/publish_hf.py",
)


@pytest.mark.parametrize("relative_path", PUBLISH_SCRIPTS)
def test_no_hardcoded_pipeline_tag(relative_path: str) -> None:
    """No publish script may emit a `pipeline_tag:` line into a card."""
    path = REPO_ROOT / relative_path
    if not path.exists():
        pytest.skip(f"{relative_path} not present")
    offenders = [
        f"{relative_path}:{n}: {line.strip()}"
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if line.lstrip().startswith("pipeline_tag:")
    ]
    assert not offenders, (
        "Seq2seq model cards must not set pipeline_tag; the Hub infers it "
        "from config.json. Offending lines:\n" + "\n".join(offenders)
    )
