"""Backward-compat shim — the rule table now lives in
:mod:`nom.compliance.laws`.

Pre-v0.3 callers imported ``RULE_TABLE`` and ``Rule`` from this
module. They still work because :class:`RuleSpec` IS the new
``Rule`` and ``RULE_TABLE`` aliases the canonical VN law's rule
tuple.

For new code: pass a custom :class:`LawSpec` to
``RiskClassifier(law=...)``. Construct your law spec by copying
:mod:`nom.compliance.laws.vn_134_2025` and replacing or extending
the ``rules`` tuple — keeps the law-as-data invariant intact.
"""

from __future__ import annotations

from nom.compliance.laws import LAW_VN_134_2025
from nom.compliance.laws._types import RuleSpec

__all__ = ["RULE_TABLE", "Rule"]


# Aliases that match the pre-refactor API.
Rule = RuleSpec
RULE_TABLE: tuple[RuleSpec, ...] = LAW_VN_134_2025.rules
