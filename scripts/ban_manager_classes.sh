#!/usr/bin/env bash
# Codify docs/architecture.md anti-pattern rule #2: no `*Manager` class
# names. Verba's five Managers are the cautionary tale (see
# docs/oss_landscape_2026q2.md). If a class genuinely needs to "manage"
# something, name it for what it owns.
#
# Run via pre-commit; safe to run by hand.
set -euo pipefail

if grep -rEn '^class [A-Z][A-Za-z0-9_]*Manager\b' --include='*.py' src/ tests/ 2>/dev/null; then
  echo
  echo 'Found Manager-suffixed class names — see docs/architecture.md anti-pattern rule #2.'
  exit 1
fi
