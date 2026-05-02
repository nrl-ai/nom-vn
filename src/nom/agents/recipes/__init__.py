"""Production-ready agent recipes.

Each function here returns a fully-configured :class:`nom.agents.Agent`
that's ready to call ``run(task)``. Recipes combine the building blocks
(``SingleAgent`` / ``OrchestratorWorkers`` / built-in tools / NLP
primitives) into the patterns operators reach for first.

Why have these at all (rather than letting users compose from scratch
every time): the building blocks are flexible but the *common* recipes
are stable. Locking them down behind a single function gives:

- One place to apply consistent system prompts, audit conventions, and
  tool schemas across deployments.
- Stable surface for documentation and demos — users can import a
  recipe and see it working in one line.
- An obvious place for EE plugins to ship domain templates (banking
  KYC, insurance claims, etc.) — see :mod:`nom_ee.recipes` in the
  enterprise repo.

Recipes are intentionally small (≤80 lines each). When a recipe
needs more configuration than fits in keyword arguments, that's the
signal to pull it apart into the building blocks directly.
"""

from __future__ import annotations

from nom.agents.recipes.compliance import compliance_screener
from nom.agents.recipes.deep_research import deep_research
from nom.agents.recipes.legal_qa import legal_qa
from nom.agents.recipes.vn_doc_analyser import vn_doc_analyser

__all__ = [
    "compliance_screener",
    "deep_research",
    "legal_qa",
    "vn_doc_analyser",
]
