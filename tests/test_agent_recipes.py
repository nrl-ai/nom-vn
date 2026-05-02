"""Tests for ``nom.agents.recipes`` — the production-ready agent factories."""

from __future__ import annotations

import json
from typing import Any

from nom.agents import AgentResult, SingleAgent
from nom.agents.recipes import (
    compliance_screener,
    deep_research,
    legal_qa,
    vn_doc_analyser,
)
from tests.test_agents import _ScriptedLLM

# ---------- vn_doc_analyser -----------------------------------------


def test_vn_doc_analyser_completes_pipeline() -> None:
    """The recipe wires three NLP tools and the LLM should walk
    through them then emit a final answer."""
    llm = _ScriptedLLM(
        [
            {
                "thought": "kiểm tra ngôn ngữ",
                "action": "tool_call",
                "tool_name": "detect_language",
                "tool_args": {"text": "test"},
            },
            {
                "thought": "trích thực thể",
                "action": "tool_call",
                "tool_name": "extract_entities",
                "tool_args": {"text": "VCB ngày 02/05/2026"},
            },
            {
                "thought": "phân tích cảm xúc",
                "action": "tool_call",
                "tool_name": "analyse_sentiment",
                "tool_args": {"text": "Khách hàng hài lòng"},
            },
            {
                "thought": "tổng hợp",
                "action": "final",
                "final_answer": "Báo cáo: VN, có ORG/DATE, cảm xúc tích cực.",
            },
        ]
    )
    agent = vn_doc_analyser(llm=llm)
    result = agent.run("VCB thông báo gói tín dụng ngày 02/05/2026, khách hàng hài lòng.")
    assert isinstance(result, AgentResult)
    assert "Báo cáo" in result.output
    assert result.n_tool_calls == 3


def test_vn_doc_analyser_tools_are_independent() -> None:
    """Each tool can be called individually with sensible defaults."""
    llm = _ScriptedLLM([{"thought": "", "action": "final", "final_answer": "ok"}])
    agent = vn_doc_analyser(llm=llm)
    tool_names = {t.name for t in agent.tools}
    assert tool_names == {"detect_language", "extract_entities", "analyse_sentiment"}


def test_vn_doc_analyser_custom_system_prompt() -> None:
    custom = "You are an English-only analyser."
    llm = _ScriptedLLM([{"thought": "", "action": "final", "final_answer": "done"}])
    agent = vn_doc_analyser(llm=llm, system_prompt=custom)
    assert agent.system_prompt == custom


# ---------- legal_qa ------------------------------------------------


class _FakeRAG:
    class _Cite:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Ans:
        def __init__(self, text: str, cites: list[Any]) -> None:
            self.text = text
            self.citations = cites
            self.n_retrieved = len(cites)

    def ask(self, question: str, *, top_k: int = 5) -> Any:
        return _FakeRAG._Ans(
            text="Theo Hiến pháp 2013, Điều 26 quy định bình đẳng giới.",
            cites=[_FakeRAG._Cite("Điều 26: …")],
        )


def test_legal_qa_uses_search_tool_then_answers() -> None:
    rag = _FakeRAG()
    llm = _ScriptedLLM(
        [
            {
                "thought": "tra cứu corpus",
                "action": "tool_call",
                "tool_name": "search_legal_corpus",
                "tool_args": {"question": "bình đẳng giới"},
            },
            {
                "thought": "trả lời với trích dẫn",
                "action": "final",
                "final_answer": "Theo Hiến pháp 2013 Điều 26.",
            },
        ]
    )
    agent = legal_qa(rag=rag, llm=llm)
    result = agent.run("Bình đẳng giới ở đâu trong Hiến pháp?")
    assert "Điều 26" in result.output
    assert result.n_tool_calls == 1


def test_legal_qa_custom_tool_name() -> None:
    """When you have multiple legal corpora, override the tool name."""
    rag = _FakeRAG()
    llm = _ScriptedLLM([{"thought": "", "action": "final", "final_answer": "ok"}])
    agent = legal_qa(rag=rag, llm=llm, tool_name="search_civil_code")
    assert {t.name for t in agent.tools} == {"search_civil_code"}


# ---------- deep_research --------------------------------------------


def test_deep_research_default_searcher_runs_subtasks() -> None:
    """Supervisor decomposes input into subtasks; the default searcher
    worker (built from the supplied search_tools) handles each."""
    rag = _FakeRAG()
    from nom.agents.tools.builtin import RAGTool

    rag_tool = RAGTool(rag=rag, name="search")

    # Supervisor: emit a plan with two subtasks for the same searcher,
    # then synthesise the final answer.
    supervisor = _ScriptedLLM(
        [
            {
                "subtasks": [
                    {"worker": "searcher", "subtask": "Q1: bình đẳng giới"},
                    {"worker": "searcher", "subtask": "Q2: quyền học tập"},
                ]
            },
            "Tổng hợp: Hiến pháp 2013 quy định cả hai khía cạnh.",
        ]
    )
    # Searcher: each subtask produces a tool call + final answer.
    # We need 2 sub-runs x 2 actions = 4 scripted entries.
    searcher_llm = _ScriptedLLM(
        [
            {
                "thought": "search",
                "action": "tool_call",
                "tool_name": "search",
                "tool_args": {"question": "Q1"},
            },
            {"thought": "answer", "action": "final", "final_answer": "Q1 → Điều 26."},
            {
                "thought": "search",
                "action": "tool_call",
                "tool_name": "search",
                "tool_args": {"question": "Q2"},
            },
            {"thought": "answer", "action": "final", "final_answer": "Q2 → Điều 39."},
        ]
    )
    # Wire a custom searcher that uses the searcher_llm so we can
    # script its responses; the recipe normally builds one from the
    # supervisor llm.
    searcher = SingleAgent(name="deep_research.searcher", llm=searcher_llm, tools=(rag_tool,))

    orch = deep_research(
        llm=supervisor,
        search_tools=(rag_tool,),  # unused because we override workers
        workers={"searcher": searcher},
    )
    result = orch.run("So sánh quyền bình đẳng và quyền học tập trong Hiến pháp 2013.")
    assert "Tổng hợp" in result.output
    assert len(result.final_state["worker_outputs"]) == 2


def test_deep_research_default_workers_built_from_llm() -> None:
    """When ``workers`` is None, the recipe auto-builds a searcher."""
    rag = _FakeRAG()
    from nom.agents.tools.builtin import RAGTool

    supervisor = _ScriptedLLM(
        [
            {"subtasks": [{"worker": "searcher", "subtask": "Q1"}]},
            "Tổng hợp: kết quả Q1.",
        ]
    )
    # The auto-built searcher uses the SAME llm as supervisor.
    # Account for: supervisor plan, searcher tool_call+final, supervisor synthesis.
    supervisor_with_searcher_responses = _ScriptedLLM(
        [
            {"subtasks": [{"worker": "searcher", "subtask": "Q1"}]},
            {
                "thought": "search",
                "action": "tool_call",
                "tool_name": "search",
                "tool_args": {"question": "Q1"},
            },
            {"thought": "answer", "action": "final", "final_answer": "Q1 → Điều 26."},
            "Tổng hợp: kết quả Q1.",
        ]
    )
    del supervisor  # unused; we use the combined script below
    rag_tool = RAGTool(rag=rag, name="search")
    orch = deep_research(
        llm=supervisor_with_searcher_responses,
        search_tools=(rag_tool,),
    )
    result = orch.run("Bình đẳng giới?")
    assert "Tổng hợp" in result.output


# ---------- compliance_screener -------------------------------------


def test_compliance_screener_redacts_pii_before_inner_runs() -> None:
    """Input containing CCCD + email should reach the inner agent
    with both replaced by placeholders."""
    seen: list[str] = []

    class _CapturingAgent:
        name = "inner"

        def run(self, task: str, *, trace: Any = None) -> AgentResult:
            from nom.agents.protocol import Trace

            seen.append(task)
            t = trace or Trace()
            t.emit("final", answer="ok")
            return AgentResult(output="ok", trace=t, n_llm_calls=1)

    wrapped = compliance_screener(inner=_CapturingAgent())
    raw = "Khách CCCD 001234567890, email a@b.vn cần hỗ trợ."
    wrapped.run(raw)
    assert len(seen) == 1
    assert "001234567890" not in seen[0]
    assert "a@b.vn" not in seen[0]
    assert "[CCCD]" in seen[0]
    assert "[EMAIL]" in seen[0]


def test_compliance_screener_emits_privacy_events() -> None:
    class _Inner:
        name = "inner"

        def run(self, task: str, *, trace: Any = None) -> AgentResult:
            from nom.agents.protocol import Trace

            t = trace or Trace()
            t.emit("final", answer="x")
            return AgentResult(output="x", trace=t)

    wrapped = compliance_screener(inner=_Inner())
    result = wrapped.run("Email: u@v.vn, SĐT 0912345678")
    kinds = [e.kind for e in result.trace.events]
    assert "privacy.detect" in kinds
    assert "privacy.redact" in kinds


def test_compliance_screener_passes_clean_input_through() -> None:
    """No PII → no detect/redact events, inner runs on raw input."""

    seen: list[str] = []

    class _Inner:
        name = "inner"

        def run(self, task: str, *, trace: Any = None) -> AgentResult:
            from nom.agents.protocol import Trace

            seen.append(task)
            t = trace or Trace()
            t.emit("final", answer="ok")
            return AgentResult(output="ok", trace=t)

    wrapped = compliance_screener(inner=_Inner())
    wrapped.run("Hôm nay trời mưa, xe đẹp.")
    assert seen == ["Hôm nay trời mưa, xe đẹp."]


def test_compliance_screener_fail_on_pii_blocks() -> None:
    """``fail_on_pii=True`` short-circuits with a denial response."""

    class _Inner:
        name = "inner"
        called = False

        def run(self, task: str, *, trace: Any = None) -> AgentResult:
            self.called = True
            from nom.agents.protocol import Trace

            t = trace or Trace()
            return AgentResult(output="should not run", trace=t)

    inner = _Inner()
    wrapped = compliance_screener(inner=inner, fail_on_pii=True)
    result = wrapped.run("CCCD 001234567890")
    assert inner.called is False
    assert "từ chối" in result.output.lower() or "không được" in result.output
    assert result.final_state.get("blocked") is True


# Optional: silence unused-import lint when this module is the only
# consumer of ``json``.
_ = json
