"""Mirror upstream Vietnamese RAG models under the ``nrl-ai`` HF org.

Pulls each model's snapshot from the upstream repo (must already be in
the local ``~/.cache/huggingface`` cache, i.e. you ``hf download``'d
it once) and re-uploads it under ``nrl-ai/<sluggified-name>`` together
with a ``NOTICE.md`` crediting the upstream authors and pinning the
source revision.

Why mirror at all (per project decision 2026-04-25):

- **Reproducibility** — the bench JSONs reference exact model IDs; a
  mirror under our org pins us to a revision we control.
- **Hosting independence** — if an upstream is yanked / renamed /
  rate-limited, our defaults keep working.
- **Brand consistency** — ``nrl-ai/vietnamese-embedding`` reads
  cleaner than ``dangvantuan/vietnamese-embedding`` in nom-vn docs.

We *do not* train, change, or rebadge weights — every mirror is a
byte-for-byte copy plus an attribution NOTICE.

Default targets (Apache 2.0 + safetensors, audited per CLAUDE.md
file-format trust ladder):

  | upstream                                | mirror                              |
  |-----------------------------------------|-------------------------------------|
  | dangvantuan/vietnamese-embedding        | nrl-ai/vietnamese-embedding         |
  | AITeamVN/Vietnamese_Embedding           | nrl-ai/vietnamese-embedding-bge-m3  |
  | BAAI/bge-reranker-v2-m3                 | nrl-ai/bge-reranker-v2-m3-mirror    |
  | namdp-ptit/ViRanker                     | nrl-ai/viranker-mirror              |

Run::

    hf auth login                                     # one-time
    python scripts/mirror_models_to_hf.py             # mirrors all four
    python scripts/mirror_models_to_hf.py --only viranker  # one model
    python scripts/mirror_models_to_hf.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

NOTICE_TEMPLATE = """\
# NOTICE

This repository is a **byte-for-byte mirror** of
[`{upstream}`](https://huggingface.co/{upstream}) (revision `{revision}`),
re-published here for reproducibility of nom-vn benchmarks and downloads.

- **Upstream license:** Apache-2.0
- **Upstream authors:** see the upstream repo's model card.
- **Mirror policy:** weights, tokenizer, and config are unchanged. We
  do not fine-tune, prune, or rebadge. The original model card README
  is preserved verbatim in `README.md`.

If you are training, fine-tuning, or doing detailed reproducibility
work, prefer the upstream repo so you receive author updates. This
mirror exists as a stable pin for downstream tools.

— [Neural Research Lab](https://nrl.ai), {year}
"""


@dataclass(frozen=True)
class MirrorTarget:
    upstream: str
    mirror: str
    short: str  # for --only filter


TARGETS = [
    MirrorTarget(
        upstream="dangvantuan/vietnamese-embedding",
        mirror="nrl-ai/vietnamese-embedding",
        short="dangvantuan",
    ),
    MirrorTarget(
        upstream="AITeamVN/Vietnamese_Embedding",
        mirror="nrl-ai/vietnamese-embedding-bge-m3",
        short="aiteamvn",
    ),
    MirrorTarget(
        upstream="BAAI/bge-reranker-v2-m3",
        mirror="nrl-ai/bge-reranker-v2-m3-mirror",
        short="bge-reranker",
    ),
    MirrorTarget(
        upstream="namdp-ptit/ViRanker",
        mirror="nrl-ai/viranker-mirror",
        short="viranker",
    ),
]


def _local_snapshot(upstream: str) -> Path | None:
    """Return the local snapshot dir for an upstream repo if cached."""
    safe = "models--" + upstream.replace("/", "--")
    base = Path.home() / ".cache" / "huggingface" / "hub" / safe / "snapshots"
    if not base.is_dir():
        return None
    snaps = sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    return snaps[0] if snaps else None


def _mirror_one(target: MirrorTarget, *, dry_run: bool) -> bool:
    snap = _local_snapshot(target.upstream)
    if snap is None:
        print(f"  ! {target.upstream}: not cached. Run: hf download {target.upstream}")
        return False
    files = sorted(p for p in snap.rglob("*") if p.is_file())
    total = sum(p.stat().st_size for p in files)
    print(f"  upstream snapshot: {snap}")
    print(f"  {len(files)} files, {total / 1e9:.2f} GB")
    if dry_run:
        print("  --dry-run: not pushing")
        return True

    from datetime import datetime, timezone

    from huggingface_hub import HfApi, create_repo

    revision = snap.name  # snapshot dirs are named after the commit hash
    notice = NOTICE_TEMPLATE.format(
        upstream=target.upstream,
        revision=revision,
        year=datetime.now(timezone.utc).year,
    )

    api = HfApi()
    create_repo(target.mirror, repo_type="model", exist_ok=True)
    api.upload_file(
        path_or_fileobj=notice.encode("utf-8"),
        path_in_repo="NOTICE.md",
        repo_id=target.mirror,
        repo_type="model",
        commit_message=f"NOTICE — mirrored from {target.upstream}@{revision[:8]}",
    )

    # Use upload_folder for atomic multi-file push.
    api.upload_folder(
        folder_path=str(snap),
        repo_id=target.mirror,
        repo_type="model",
        commit_message=f"mirror {target.upstream}@{revision[:8]}",
    )
    print(f"  → https://huggingface.co/{target.mirror}")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--only", default=None, help="short name of one target to mirror")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    targets = TARGETS
    if args.only:
        targets = [t for t in targets if t.short == args.only]
        if not targets:
            print(f"unknown --only: {args.only!r}", file=sys.stderr)
            return 2

    ok = True
    for t in targets:
        print(f"\n{t.upstream}  →  {t.mirror}")
        if not _mirror_one(t, dry_run=args.dry_run):
            ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
