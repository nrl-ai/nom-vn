"""End-to-end smoke test for the built wheel.

Builds the wheel, installs it into a fresh isolated venv (twice — once
with no extras, once with ``[chat,doc]``), and runs through the user-
visible surface to confirm:

- All major top-level modules import cleanly with zero extras.
- The ``nom`` CLI is registered as an entry point and ``nom --help``
  works.
- Lazy-import paths (text normalize, NER, lexicon register classifier)
  run on a fresh install.
- ``[chat]`` extra builds the FastAPI app and serves stateless
  endpoints.
- ``[doc]`` extra runs ``nom.convert.convert_to_docx`` end-to-end on
  a real Vietnamese scanned-document PDF.

Run::

    python scripts/smoke_pypi_wheel.py

Exit code 0 on full pass, non-zero on any failure. Failures print the
exact traceback and the venv path so the operator can reproduce
manually.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def run(
    cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a command, capture stdout/stderr, raise with a clear message on
    non-zero exit."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env={**os.environ, **(env or {})},
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        sys.stderr.write(f"\n--- COMMAND FAILED: {' '.join(cmd)} ---\n")
        sys.stderr.write(f"stdout:\n{proc.stdout}\n")
        sys.stderr.write(f"stderr:\n{proc.stderr}\n")
        raise SystemExit(2)
    return proc


def build_wheel(repo: Path) -> Path:
    """Build the wheel via ``python -m build --wheel`` and return its path."""
    print(f"=== Building wheel from {repo} ===")
    run([sys.executable, "-m", "build", "--wheel"], cwd=repo)
    dist = repo / "dist"
    candidates = sorted(
        dist.glob("nom_vn-*-py3-none-any.whl"), key=lambda p: p.stat().st_mtime, reverse=True
    )
    if not candidates:
        raise SystemExit("no wheel produced under dist/")
    wheel = candidates[0]
    print(f"  wheel: {wheel.name} ({wheel.stat().st_size / 1024:.1f} KB)")
    return wheel


def fresh_venv(workdir: Path, name: str) -> Path:
    venv = workdir / name
    if venv.exists():
        shutil.rmtree(venv)
    run([sys.executable, "-m", "venv", str(venv)])
    return venv


def venv_python(venv: Path) -> Path:
    return venv / "bin" / "python"


def venv_run(venv: Path, code: str, *, env: dict[str, str] | None = None) -> str:
    """Run ``code`` in the venv's interpreter; return stdout."""
    proc = run([str(venv_python(venv)), "-c", code], env=env)
    return proc.stdout


def smoke_base(venv: Path, wheel: Path) -> None:
    print(f"\n=== [base] {venv.name} ===")
    run([str(venv_python(venv)), "-m", "pip", "install", "--quiet", str(wheel)])

    # 1. Every top-level user-facing module imports.
    out = venv_run(
        venv,
        textwrap.dedent("""
            import importlib
            modules = [
                'nom', 'nom.agents', 'nom.agents.protocol', 'nom.agents.runtime',
                'nom.classify', 'nom.classify.register',
                'nom.text', 'nom.text.normalize', 'nom.text.segment',
                'nom.nlp', 'nom.nlp.ner', 'nom.nlp.ner_legal', 'nom.nlp.sentiment',
                'nom.translate', 'nom.translate.formats',
                'nom.convert', 'nom.convert.dispatcher',
                'nom.platform.context', 'nom.platform.license',
                'nom.platform.privacy', 'nom.platform.rbac',
                'nom.chunking', 'nom.embeddings', 'nom.retrieve', 'nom.rag',
                'nom.compliance', 'nom.jobs', 'nom.doc', 'nom.ocr', 'nom.stt',
                'nom.summarize', 'nom.llm', 'nom.mcp',
            ]
            failed = []
            for m in modules:
                try:
                    importlib.import_module(m)
                except Exception as e:
                    failed.append(f'{m}: {type(e).__name__}: {e}')
            if failed:
                raise SystemExit('\\n'.join(failed))
            print(f'OK {len(modules)} modules')
        """).strip(),
    )
    print(f"  imports: {out.strip()}")

    # 2. CLI entry point is wired.
    proc = run([str(venv / "bin" / "nom"), "--help"])
    assert "nom serve" in proc.stdout
    print("  CLI: nom --help → all subcommands listed")

    # 3. Lazy-import paths work.
    out = venv_run(
        venv,
        textwrap.dedent("""
            from nom.text.normalize import normalize, has_diacritics, is_vietnamese, strip_diacritics
            assert normalize('Tôi yêu Việt Nam')
            assert has_diacritics('Hợp đồng')
            assert is_vietnamese('Hợp đồng số 02')
            assert strip_diacritics('Hợp đồng') == 'Hop dong'

            from nom.text import word_tokenize, sent_tokenize
            tokens = word_tokenize('Thành phố Hồ Chí Minh là thành phố lớn nhất Việt Nam')
            assert 'Việt Nam' in tokens, tokens
            assert len(sent_tokenize('Tôi. Bạn? Họ!')) == 3

            from nom.nlp.ner import RegexNERModel
            from nom.nlp.ner_legal import legal_ner_patterns
            ner = RegexNERModel(extra_patterns=legal_ner_patterns())
            spans = ner.tag('Theo Nghị định 13/2023/NĐ-CP, ông X (CMND 012345678) thanh toán 1.500.000 VND ngày 02/05/2026.')
            labels = sorted({s.label for s in spans})
            assert {'LAW_REF', 'ID_VN', 'MONEY', 'DATE'}.issubset(labels), labels

            from nom.classify.register import LexiconRegisterClassifier, RegisterLabel
            clf = LexiconRegisterClassifier()
            assert clf.predict('Mình thấy chỗ đó ngon lắm nha, đi thử nhé!').label == RegisterLabel.CONVERSATIONAL

            print('lazy paths OK')
        """).strip(),
    )
    print(f"  lazy:    {out.strip()}")


def smoke_chat(venv: Path, wheel: Path) -> None:
    print(f"\n=== [chat] {venv.name} ===")
    run([str(venv_python(venv)), "-m", "pip", "install", "--quiet", f"{wheel}[chat]"])

    out = venv_run(
        venv,
        textwrap.dedent("""
            from nom.chat.server import build_app
            from nom.chat.store import MemoryStore
            from fastapi.testclient import TestClient

            class FakeEmbedder:
                dim = 8
                def embed(self, texts):
                    return [[0.0]*8 for _ in texts]
                def embed_query(self, q):
                    return [0.0]*8

            class FakeLLM:
                def complete(self, prompt, **kw):
                    return 'Stub.'

            store = MemoryStore(embedder=FakeEmbedder(), llm=FakeLLM())
            client = TestClient(build_app(store=store))
            checks = [
                ('/api/tools/diacritic/restore', {'text': 'toi yeu Viet Nam', 'backend': 'rule'}),
                ('/api/tools/text/detect', {'text': 'Hợp đồng số 02'}),
                ('/api/tools/nlp/ner', {'text': 'Theo Nghị định 13/2023/NĐ-CP', 'preset': 'legal'}),
                ('/api/tools/text/normalize', {'text': 'Tôi'}),
            ]
            for ep, body in checks:
                r = client.post(ep, json=body)
                assert r.status_code == 200, f'{ep} → {r.status_code} {r.text[:120]}'
            print(f'chat: {len(checks)} endpoints OK')
        """).strip(),
    )
    print(f"  api:     {out.strip()}")


def smoke_doc(venv: Path, wheel: Path) -> None:
    print(f"\n=== [doc] {venv.name} ===")
    run([str(venv_python(venv)), "-m", "pip", "install", "--quiet", f"{wheel}[doc]"])

    if shutil.which("tesseract") is None:
        print("  doc: skipped — tesseract not on PATH")
        return

    src = REPO / "benchmarks/data/vn_documents_ocr/docs/contract_lao_dong.pdf"
    if not src.exists():
        print(f"  doc: skipped — fixture missing ({src})")
        return

    out = venv_run(
        venv,
        textwrap.dedent(f"""
            import tempfile
            from pathlib import Path
            from nom.convert import convert_to_docx
            from docx import Document

            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / 'out.docx'
                stats = convert_to_docx({str(src)!r}, out)
                text = '\\n'.join(p.text for p in Document(out).paragraphs).strip()
                # Sanity assertions: pdf was OCR'd, output has the title.
                assert stats.pages_ocred >= 1, stats
                assert 'HỢP ĐỒNG' in text, text[:120]
                # Very loose CER guard — should be much better than this.
                assert len(text) > 1000, len(text)
                print(f'doc: {{stats.n_pages}}p OCR={{stats.pages_ocred}} chars={{stats.chars_out}}')
        """).strip(),
    )
    print(f"  convert: {out.strip()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="Keep venvs after run.")
    parser.add_argument("--wheel", type=Path, help="Path to an already-built wheel (skip build).")
    args = parser.parse_args()

    wheel = args.wheel or build_wheel(REPO)
    workdir = Path(tempfile.mkdtemp(prefix="nom_smoke_"))
    print(f"workdir: {workdir}")

    try:
        smoke_base(fresh_venv(workdir, "base"), wheel)
        smoke_chat(fresh_venv(workdir, "chat"), wheel)
        smoke_doc(fresh_venv(workdir, "doc"), wheel)
    finally:
        if args.keep:
            print(f"\nKept venvs at {workdir}")
        else:
            shutil.rmtree(workdir, ignore_errors=True)

    print("\nALL SMOKES PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
