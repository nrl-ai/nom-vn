#!/usr/bin/env bash
# Build the React UI and stage the bundle for wheel inclusion.
# Run this before `pip wheel .` or `python -m build`.
#
# Outputs:
#   ui/dist/           — Vite build output (used in dev, served via parent walk)
#   src/nom/chat/ui_dist/ — copy of ui/dist used at packaging time
#
# Idempotent. Safe to re-run.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
UI_DIR="$REPO_ROOT/ui"
PKG_DIST="$REPO_ROOT/src/nom/chat/ui_dist"

if [ ! -d "$UI_DIR" ]; then
  echo "ui/ directory not found at $UI_DIR" >&2
  exit 1
fi

echo "→ pnpm install (ui)"
( cd "$UI_DIR" && pnpm install --frozen-lockfile 2>/dev/null || pnpm install )

echo "→ pnpm build (ui)"
( cd "$UI_DIR" && pnpm build )

echo "→ staging dist into package"
rm -rf "$PKG_DIST"
mkdir -p "$PKG_DIST"
cp -R "$UI_DIR/dist/." "$PKG_DIST/"

echo "✔ UI bundle ready at $PKG_DIST"
