"""End-to-end demo of ``nom.agents.recipes``.

Run from a checkout::

    python examples/recipes_demo.py

Walks through every recipe with a scripted LLM so the demo runs
without Ollama / cloud LLM. Replace :class:`_ScriptedLLM` with
:class:`nom.llm.Ollama` (or any other ``nom.llm.LLM``) for live
multi-step reasoning.

Recipes covered:

1. ``vn_doc_analyser`` — language + entities + sentiment + report
2. ``legal_qa`` — RAG-grounded Q&A with citations
3. ``compliance_screener`` — PII redaction wrapper around any agent
4. ``deep_research`` — orchestrator-workers research over a corpus
"""

from __future__ import annotations

import json
from typing import Any

from nom.agents import AgentResult
from nom.agents.recipes import (
    compliance_screener,
    deep_research,
    legal_qa,
    vn_doc_analyser,
)

# ---------- Scripted LLM: drives every demo deterministically ------


class _ScriptedLLM:
    """Returns a queue of canned responses. The script is set per
    section so the same class powers every recipe demo."""

    name = "scripted-demo"

    def __init__(self, responses: list[Any] | None = None) -> None:
        self._responses: list[Any] = list(responses or [])
        self.calls: int = 0

    def script(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls = 0

    def complete(self, prompt: str, *, schema: Any | None = None, max_tokens: int = 2048) -> str:
        del prompt, schema, max_tokens
        if not self._responses:
            return json.dumps({"thought": "done", "action": "final", "final_answer": "(end)"})
        self.calls += 1
        nxt = self._responses.pop(0)
        if isinstance(nxt, dict):
            return json.dumps(nxt, ensure_ascii=False)
        return str(nxt)


# ---------- 1. vn_doc_analyser --------------------------------------


def demo_doc_analyser() -> None:
    print("\n=== 1. vn_doc_analyser ===")
    text = "VCB thông báo gói tín dụng 1.500.000 VND ngày 02/05/2026, khách hàng rất hài lòng."
    print(f"  Input: {text}")

    llm = _ScriptedLLM(
        [
            {
                "thought": "kiểm tra ngôn ngữ",
                "action": "tool_call",
                "tool_name": "detect_language",
                "tool_args": {"text": text},
            },
            {
                "thought": "trích thực thể",
                "action": "tool_call",
                "tool_name": "extract_entities",
                "tool_args": {"text": text},
            },
            {
                "thought": "phân tích cảm xúc",
                "action": "tool_call",
                "tool_name": "analyse_sentiment",
                "tool_args": {"text": text},
            },
            {
                "thought": "tổng hợp",
                "action": "final",
                "final_answer": (
                    "Tiếng Việt. Thực thể: VCB (ORG), 1.500.000 VND (MONEY), "
                    "02/05/2026 (DATE). Cảm xúc: tích cực. Nhận xét: thông báo "
                    "tín dụng chính thức, phản hồi khách hàng tốt."
                ),
            },
        ]
    )

    agent = vn_doc_analyser(llm=llm)
    result = agent.run(text)
    _print_result(result)


# ---------- 2. legal_qa ---------------------------------------------


def demo_legal_qa() -> None:
    print("\n=== 2. legal_qa ===")

    class _Cite:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Ans:
        def __init__(self, text: str, cites: list[Any]) -> None:
            self.text = text
            self.citations = cites
            self.n_retrieved = len(cites)

    class _FakeRAG:
        def ask(self, question: str, *, top_k: int = 5) -> Any:
            return _Ans(
                "Theo Hiến pháp 2013, Điều 26: nam, nữ bình đẳng về mọi mặt.",
                [
                    _Cite(
                        "Điều 26: Công dân nam, nữ bình đẳng về mọi mặt — chính trị, "
                        "dân sự, kinh tế, văn hoá, xã hội và gia đình."
                    )
                ],
            )

    question = "Hiến pháp 2013 quy định gì về bình đẳng giới?"
    print(f"  Question: {question}")

    llm = _ScriptedLLM(
        [
            {
                "thought": "tra cứu luật",
                "action": "tool_call",
                "tool_name": "search_legal_corpus",
                "tool_args": {"question": question},
            },
            {
                "thought": "trả lời với trích dẫn",
                "action": "final",
                "final_answer": (
                    "Theo Hiến pháp 2013, Điều 26 quy định công dân nam, nữ "
                    "bình đẳng về mọi mặt — chính trị, dân sự, kinh tế, văn hoá, "
                    "xã hội và gia đình. (Điều 26)"
                ),
            },
        ]
    )

    agent = legal_qa(rag=_FakeRAG(), llm=llm)
    result = agent.run(question)
    _print_result(result)


# ---------- 3. compliance_screener ----------------------------------


def demo_compliance_screener() -> None:
    print("\n=== 3. compliance_screener ===")

    class _InnerLLM:
        name = "inner"

        def run(self, task: str, *, trace: Any = None) -> AgentResult:
            from nom.agents.protocol import Trace

            t = trace or Trace()
            t.emit("final", answer=f"Đã xử lý: {task[:80]}…")
            return AgentResult(output=f"Đã xử lý: {task[:80]}…", trace=t)

    raw = (
        "Khách hàng tên Nguyễn Văn A, CCCD 001234567890, email a@vcb.vn, "
        "SĐT 0912345678 cần hỗ trợ vay vốn."
    )
    print(f"  Raw input: {raw}")

    wrapped = compliance_screener(inner=_InnerLLM())
    result = wrapped.run(raw)
    print(f"  → forwarded to inner agent: {result.output}")
    print("  Privacy events:")
    for ev in result.trace.events:
        if ev.kind.startswith("privacy."):
            print(f"    [{ev.kind}] {ev.payload}")


def demo_compliance_screener_block() -> None:
    print("\n=== 3b. compliance_screener (fail_on_pii=True) ===")

    class _Inner:
        name = "inner"

        def run(self, task: str, *, trace: Any = None) -> AgentResult:
            raise AssertionError("inner must NOT run when fail_on_pii blocks")

    raw = "CCCD 001234567890 cần được tra cứu."
    wrapped = compliance_screener(inner=_Inner(), fail_on_pii=True)
    result = wrapped.run(raw)
    print("  Input had PII → blocked.")
    print(f"  Response: {result.output}")
    print(f"  blocked={result.final_state.get('blocked')} kinds={result.final_state.get('kinds')}")


# ---------- 4. deep_research ----------------------------------------


def demo_deep_research() -> None:
    print("\n=== 4. deep_research ===")

    class _Cite:
        def __init__(self, t: str) -> None:
            self.text = t

    class _Ans:
        def __init__(self, t: str, c: list[Any]) -> None:
            self.text = t
            self.citations = c
            self.n_retrieved = len(c)

    class _FakeRAG:
        def ask(self, q: str, *, top_k: int = 5) -> Any:
            return _Ans(f"Nguồn nói: {q!r} là một chủ đề pháp lý.", [_Cite("…trích dẫn…")])

    from nom.agents import SingleAgent
    from nom.agents.tools.builtin import RAGTool

    rag_tool = RAGTool(rag=_FakeRAG(), name="search")

    supervisor = _ScriptedLLM(
        [
            # 1. Plan
            {
                "subtasks": [
                    {"worker": "searcher", "subtask": "Bình đẳng giới trong Hiến pháp 2013"},
                    {"worker": "searcher", "subtask": "Quyền học tập trong Hiến pháp 2013"},
                ]
            },
            # 4. Synthesis (after both workers return)
            (
                "Tổng hợp nghiên cứu sâu:\n"
                "- Hiến pháp 2013 quy định bình đẳng giới ở Điều 26.\n"
                "- Quyền học tập ở Điều 39.\n"
                "Hai điều này phối hợp đảm bảo quyền tiếp cận giáo dục công bằng."
            ),
        ]
    )

    searcher_llm = _ScriptedLLM(
        [
            {
                "thought": "search subtask 1",
                "action": "tool_call",
                "tool_name": "search",
                "tool_args": {"question": "Bình đẳng giới"},
            },
            {"thought": "answer", "action": "final", "final_answer": "Điều 26."},
            {
                "thought": "search subtask 2",
                "action": "tool_call",
                "tool_name": "search",
                "tool_args": {"question": "Quyền học tập"},
            },
            {"thought": "answer", "action": "final", "final_answer": "Điều 39."},
        ]
    )

    searcher = SingleAgent(name="searcher", llm=searcher_llm, tools=(rag_tool,))
    orch = deep_research(
        llm=supervisor,
        search_tools=(rag_tool,),
        workers={"searcher": searcher},
    )

    question = "So sánh bình đẳng giới và quyền học tập trong Hiến pháp 2013"
    print(f"  Question: {question}")
    result = orch.run(question)
    _print_result(result)


# ---------- helpers --------------------------------------------------


def _print_result(result: AgentResult) -> None:
    print(f"  Tool calls: {result.n_tool_calls}, LLM calls: {result.n_llm_calls}")
    print(f"  Output:\n    {result.output}")


def main() -> int:
    demo_doc_analyser()
    demo_legal_qa()
    demo_compliance_screener()
    demo_compliance_screener_block()
    demo_deep_research()
    print("\nAll recipe demos completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
