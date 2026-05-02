"""``legal_qa`` — RAG-grounded Q&A over a Vietnamese legal corpus.

Hands the LLM one tool — ``search_legal_corpus`` — that wraps a
``nom.rag.RAG`` index. The system prompt enforces "search first,
answer with citations" so the agent doesn't hallucinate articles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from nom.agents.patterns.single import SingleAgent
from nom.agents.tools.builtin import RAGTool

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = ["legal_qa"]


_SYSTEM_PROMPT = (
    "Bạn là cố vấn pháp luật, sử dụng kho văn bản đã được lập chỉ mục. "
    "Quy tắc tuyệt đối:\n"
    "- LUÔN dùng `search_legal_corpus` trước khi trả lời câu hỏi pháp lý.\n"
    "- Chỉ trả lời dựa trên kết quả tra cứu; nếu kết quả không đủ rõ, "
    'nói thẳng "không đủ cơ sở để trả lời" thay vì đoán.\n'
    "- Trích dẫn rõ điều / khoản nguồn trong câu trả lời cuối.\n"
    "- Trả lời bằng tiếng Việt, ngắn gọn, có cấu trúc."
)


def legal_qa(
    *,
    rag: Any,
    llm: LLM,
    name: str = "legal_advisor",
    tool_name: str = "search_legal_corpus",
    max_steps: int = 6,
    system_prompt: str | None = None,
) -> SingleAgent:
    """Return a SingleAgent that answers legal questions from a RAG index.

    Args:
        rag: a ``nom.rag.RAG`` instance (already indexed).
        llm: the answering LLM (wrap with ``AuditedLLM`` in production
            to land every call in the chain-signed audit trail).
        name: agent name surfaced in traces and audit events.
        tool_name: name advertised to the LLM for the search tool —
            override when you have multiple legal corpora exposed
            (``search_civil_code``, ``search_tax_code``, …).
        max_steps: tool-call budget. Default 6 covers a typical
            research + clarification + answer cycle; legal questions
            occasionally need a second search for a referenced
            article.
        system_prompt: override the default VN legal prompt.
    """
    rag_tool = RAGTool(rag=rag, name=tool_name)
    return SingleAgent(
        name=name,
        llm=llm,
        # See vn_doc_analyser for the cast rationale.
        tools=(rag_tool,),  # type: ignore[arg-type]
        max_steps=max_steps,
        system_prompt=system_prompt or _SYSTEM_PROMPT,
    )
