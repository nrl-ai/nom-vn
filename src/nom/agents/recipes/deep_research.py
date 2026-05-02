"""``deep_research`` — orchestrator-workers deep research over multiple sources.

Three-role decomposition (Anthropic's orchestrator-workers pattern):

- **planner** (the supervisor LLM) decomposes the question into
  research sub-questions and dispatches them to specialists.
- **searcher** (one or more sub-agents) is a SingleAgent with one or
  more search tools (RAG, web, MCP) — answers each sub-question.
- **synthesiser** (the supervisor again) merges the worker outputs
  into a single answer with citations.

Use this when the input is open-ended ("What are the main risks of …",
"How does VN regulation X compare to EU GDPR") and one searcher pass
isn't enough.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from nom.agents.patterns.orchestrator import OrchestratorWorkers
from nom.agents.patterns.single import SingleAgent
from nom.agents.protocol import Agent, Tool

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = ["deep_research"]


_WORKER_PROMPT = (
    "Bạn là một searcher. Với mỗi sub-question, dùng công cụ tra cứu "
    "đã được cung cấp để tìm thông tin, rồi trả lời ngắn gọn (≤4 dòng) "
    "kèm trích dẫn từ kết quả tra cứu. Không bịa thông tin."
)


def deep_research(
    *,
    llm: LLM,
    search_tools: tuple[Tool, ...],
    workers: Mapping[str, Agent] | None = None,
    name: str = "deep_research",
    max_subtasks: int = 4,
    max_workers: int = 4,
    worker_max_steps: int = 6,
) -> OrchestratorWorkers:
    """Return an OrchestratorWorkers ready to handle research queries.

    Args:
        llm: the supervisor LLM (also used by the default searcher
            worker if ``workers`` is None). Wrap with ``AuditedLLM``
            in production.
        search_tools: tools the default ``searcher`` worker can use.
            Typical: ``(RAGTool(my_rag),)`` plus optional MCP-backed
            web search.
        workers: optional explicit worker map. When None we ship a
            single ``searcher`` SingleAgent built from ``llm`` and
            ``search_tools``. Pass a custom map to mix specialist
            agents (legal_advisor, finance_analyst, …).
        name: orchestrator name surfaced in audit events.
        max_subtasks: cap on planner-emitted subtasks.
        max_workers: thread-pool size for parallel worker dispatch.
        worker_max_steps: per-worker step budget.
    """
    if workers is None:
        workers = {
            "searcher": SingleAgent(
                name=f"{name}.searcher",
                llm=llm,
                tools=search_tools,
                max_steps=worker_max_steps,
                system_prompt=_WORKER_PROMPT,
            )
        }

    return OrchestratorWorkers(
        name=name,
        llm=llm,
        workers=dict(workers),
        max_subtasks=max_subtasks,
        max_workers=max_workers,
    )
