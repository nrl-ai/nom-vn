"""``vn_doc_analyser`` — extract structure + sentiment from a VN document.

The recipe wires three NLP primitives (language detection, NER, sentiment)
as agent tools and instructs the LLM to use them in sequence. Useful for:

- Triaging customer feedback (sentiment + entities mentioned)
- Summarising legal / financial documents (entities, dates, amounts)
- Pre-flight checks before routing a document to a heavier pipeline

Built on :class:`SingleAgent` so the LLM decides the order of tool
calls; an LLM that doesn't need NER on a particular input can skip it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, ClassVar

from nom.agents.patterns.single import SingleAgent
from nom.agents.protocol import ToolError
from nom.nlp import LexiconSentimentModel, RegexNERModel, detect_language

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = ["vn_doc_analyser"]


_SYSTEM_PROMPT = (
    "Bạn là trợ lý phân tích văn bản tiếng Việt. Với mỗi yêu cầu, hãy:\n"
    "1. Dùng `detect_language` để xác nhận ngôn ngữ đầu vào.\n"
    "2. Dùng `extract_entities` để trích xuất tổ chức, ngày tháng, "
    "số tiền nổi bật.\n"
    "3. Dùng `analyse_sentiment` để đánh giá thái độ chung.\n"
    "4. Tổng hợp một báo cáo ngắn (≤6 dòng): ngôn ngữ, các thực thể "
    "quan trọng, cảm xúc, nhận xét tổng quan.\n"
    "Trả lời bằng tiếng Việt. Nếu một công cụ trả lỗi, đọc lỗi rồi "
    "thử cách khác hoặc dừng và báo cho người dùng."
)


class _NERTool:
    name = "extract_entities"
    description = (
        "Extract Vietnamese named entities (ORG, DATE, MONEY, …). "
        "Returns a list of {label, text, start, end}."
    )
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def __init__(self) -> None:
        self._model = RegexNERModel()

    def call(self, args: Mapping[str, Any]) -> Any:
        text = args.get("text")
        if not isinstance(text, str) or not text:
            raise ToolError("`text` is required")
        return [
            {"label": s.label, "text": s.text, "start": s.start, "end": s.end}
            for s in self._model.tag(text)
        ]


class _SentimentTool:
    name = "analyse_sentiment"
    description = (
        "Classify Vietnamese text sentiment (positive / neutral / negative). "
        "Returns {label, score}."
    )
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def __init__(self) -> None:
        self._model = LexiconSentimentModel()

    def call(self, args: Mapping[str, Any]) -> Any:
        text = args.get("text")
        if not isinstance(text, str) or not text:
            raise ToolError("`text` is required")
        r = self._model.predict(text)
        return {"label": r.label.value, "score": r.score}


class _LanguageTool:
    name = "detect_language"
    description = "Detect the dominant language code (vi/en/zh/ja/ko/und)."
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def call(self, args: Mapping[str, Any]) -> Any:
        text = args.get("text")
        if not isinstance(text, str) or not text:
            raise ToolError("`text` is required")
        d = detect_language(text)
        return {"language": d.code, "confidence": d.confidence}


def vn_doc_analyser(
    *,
    llm: LLM,
    name: str = "vn_doc_analyser",
    max_steps: int = 6,
    system_prompt: str | None = None,
) -> SingleAgent:
    """Return a SingleAgent that analyses a VN document end-to-end.

    Args:
        llm: any ``nom.llm.LLM`` (wrap with ``AuditedLLM`` in production).
        name: agent name surfaced in audit logs and traces.
        max_steps: tool-call budget; the default of 6 leaves room for
            an exploration step + the three planned tool calls + a
            final synthesis.
        system_prompt: override the default VN-tuned prompt.
    """
    return SingleAgent(
        name=name,
        llm=llm,
        # mypy can't narrow concrete tool classes to the Tool Protocol
        # without a runtime check; the cast is safe because each class
        # in the tuple satisfies the duck-typed Protocol.
        tools=(_LanguageTool(), _NERTool(), _SentimentTool()),  # type: ignore[arg-type]
        max_steps=max_steps,
        system_prompt=system_prompt or _SYSTEM_PROMPT,
    )
