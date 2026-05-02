"""``nom.agents`` — typed multi-agent runtime with audit-trail.

Built native (no LangChain / LangGraph dependency) on top of:
- ``nom.llm.LLM`` Protocol — model abstraction
- ``nom.compliance.AuditedLLM`` — every model call audited
- ``nom.platform`` — auth + user context propagation

Six patterns from Anthropic's "Building Effective Agents":

- :class:`SingleAgent` — LLM + tools loop. Use this for "answer
  questions based on files" (with a RAG tool) and "take actions"
  (with action tools). 90% of use cases.
- :class:`ChainAgent` — sequential prompt chaining.
- :class:`RouteAgent` — classify → dispatch.
- :class:`ParallelAgent` — fan-out + aggregate.
- :class:`OrchestratorWorkers` — supervisor delegates to specialists.
- :class:`EvaluatorOptimizer` — generator-critic loop.

Each pattern composes ``Tool`` and produces auditable ``Trace``s.
``Tool`` is a plain Protocol — anything with ``name``, ``description``,
``schema``, and a ``call`` method works. Built-in tools wrap
``nom.rag``, ``nom.doc``, simple HTTP, and shell-side actions.
"""

from __future__ import annotations

from nom.agents.patterns.chain import ChainAgent
from nom.agents.patterns.evaluator import EvaluatorOptimizer
from nom.agents.patterns.orchestrator import OrchestratorWorkers
from nom.agents.patterns.parallel import ParallelAgent, VotingAgent
from nom.agents.patterns.route import RouteAgent
from nom.agents.patterns.single import SingleAgent
from nom.agents.protocol import (
    Agent,
    AgentResult,
    Tool,
    ToolCall,
    ToolError,
    ToolResult,
    Trace,
    TraceEvent,
)
from nom.agents.tools.builtin import HTTPGetTool, PythonEvalTool, RAGTool

__all__ = [
    "Agent",
    "AgentResult",
    "ChainAgent",
    "EvaluatorOptimizer",
    "HTTPGetTool",
    "OrchestratorWorkers",
    "ParallelAgent",
    "PythonEvalTool",
    "RAGTool",
    "RouteAgent",
    "SingleAgent",
    "Tool",
    "ToolCall",
    "ToolError",
    "ToolResult",
    "Trace",
    "TraceEvent",
    "VotingAgent",
]
