"""Six pattern classes from Anthropic's "Building Effective Agents".

Each pattern is a small file (≤200 LOC) that satisfies the
:class:`nom.agents.Agent` Protocol. They compose freely — an
``OrchestratorWorkers`` can route to a ``SingleAgent`` whose tool is
itself another ``ChainAgent``.
"""

from __future__ import annotations
