"""Single-agent pattern: LLM + tools loop.

This is the workhorse — 90% of "let an AI answer questions and take
actions" work fits here. Build with ``RAGTool`` for file Q&A, plus
whatever action tools are appropriate (HTTP, file write, custom
business logic).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nom.agents.protocol import AgentResult, Tool, Trace
from nom.agents.runtime import ToolLoop

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = ["SingleAgent"]


@dataclass
class SingleAgent:
    """LLM-driven loop that picks tools and emits a final answer.

    Compose with :class:`nom.agents.RAGTool` for file Q&A, plus any
    action tool that satisfies the :class:`Tool` Protocol::

        from nom.llm import Ollama
        from nom.compliance import AuditedLLM, AuditLog, RiskTier
        from nom.rag import RAG
        from nom.agents import RAGTool, SingleAgent

        rag = RAG.from_documents(["benchmarks/data/legal_vi/hien_phap_2013.txt"])
        audit = AuditLog.sqlite("audit.db", signing_key=key)
        llm = AuditedLLM(Ollama("qwen3:8b"), audit_log=audit, risk_tier=RiskTier.MEDIUM)

        agent = SingleAgent(
            name="legal_advisor",
            llm=llm,
            tools=(RAGTool(rag, name="search_legal"),),
            system_prompt="Bạn là cố vấn pháp luật. Dùng search_legal để tra cứu.",
        )
        result = agent.run("Hiến pháp 2013 quy định gì về bình đẳng giới?")
        print(result.output)
        print(f"Tool calls: {result.n_tool_calls}, LLM calls: {result.n_llm_calls}")
    """

    name: str
    llm: LLM
    tools: tuple[Tool, ...] = ()
    max_steps: int = 8
    system_prompt: str | None = None
    _loop: ToolLoop | None = field(default=None, init=False, repr=False)

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        if trace is None:
            trace = Trace()
        trace.emit("start", agent=self.name, task=task[:200])
        if self._loop is None:
            self._loop = ToolLoop(
                llm=self.llm,
                tools=self.tools,
                max_steps=self.max_steps,
                system_prompt=self.system_prompt,
            )
        try:
            answer, stats = self._loop.run(task, trace=trace)
        except Exception as exc:
            trace.emit("error", agent=self.name, exception=type(exc).__name__, message=str(exc))
            trace.emit("end", agent=self.name, ok=False)
            raise
        trace.emit("end", agent=self.name, ok=True)
        return AgentResult(
            output=answer,
            trace=trace,
            n_tool_calls=stats["n_tool_calls"],
            n_llm_calls=stats["n_llm_calls"],
        )
