"""Tests for ``nom.agents`` — typed Protocol surface, runtime, patterns,
and the file-Q&A + actions agent path the user explicitly asked for.

We build everything against a programmable fake LLM so tests are
deterministic. A real-LLM smoke (Ollama qwen3:8b) lives in
``tests/test_agents_real.py`` and is gated on env var.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nom.agents import (
    AgentResult,
    ChainAgent,
    EvaluatorOptimizer,
    HTTPGetTool,
    OrchestratorWorkers,
    ParallelAgent,
    PythonEvalTool,
    RAGTool,
    RouteAgent,
    SingleAgent,
    Tool,
    ToolError,
    VotingAgent,
)
from nom.agents.tools.builtin import FileReadTool

# ---------- Programmable LLM ------------------------------------------


class _ScriptedLLM:
    """Returns the next scripted response per call.

    For tool-loop tests we script JSON actions; for chain / evaluator
    tests we script raw strings.
    """

    name = "scripted"

    def __init__(self, responses: list[str | dict[str, Any]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    def complete(self, prompt: str, *, schema: Any | None = None, max_tokens: int = 2048) -> str:
        self.calls.append({"prompt": prompt[:200], "schema_keys": list(schema or {})})
        if not self._responses:
            raise AssertionError("ScriptedLLM ran out of responses")
        nxt = self._responses.pop(0)
        if isinstance(nxt, dict):
            return json.dumps(nxt, ensure_ascii=False)
        return nxt


# ---------- Protocol contracts ----------------------------------------


def test_pythoneval_tool_satisfies_protocol() -> None:
    assert isinstance(PythonEvalTool(), Tool)


def test_pythoneval_computes_arithmetic() -> None:
    t = PythonEvalTool()
    out = t.call({"expr": "(120 * 1.1 + 50) / 3"})
    assert out["value"] == pytest.approx((120 * 1.1 + 50) / 3)


def test_pythoneval_rejects_function_calls() -> None:
    t = PythonEvalTool()
    with pytest.raises(ToolError, match="disallowed"):
        t.call({"expr": "__import__('os').system('echo pwned')"})


def test_pythoneval_rejects_names() -> None:
    with pytest.raises(ToolError, match="disallowed"):
        PythonEvalTool().call({"expr": "abs(-1)"})  # 'abs' is a name


def test_file_read_tool_blocks_path_escape(tmp_path: Path) -> None:
    (tmp_path / "ok.txt").write_text("hello", encoding="utf-8")
    t = FileReadTool(root=tmp_path)
    out = t.call({"path": "ok.txt"})
    assert out["content"] == "hello"
    with pytest.raises(ToolError, match="escapes root"):
        t.call({"path": "../etc/passwd"})


def test_http_get_tool_enforces_allowlist() -> None:
    t = HTTPGetTool(allowed_hosts=("intranet.example.vn",))
    with pytest.raises(ToolError, match="not in allow-list"):
        t.call({"url": "https://attacker.example/x"})


# ---------- SingleAgent: file-Q&A + actions ---------------------------


class _FakeRAG:
    """Mimics the surface ``RAGTool`` reads — ``ask`` → answer with citations."""

    class _Citation:
        def __init__(self, text: str) -> None:
            self.text = text

    class _Answer:
        def __init__(self, text: str, citations: list[Any]) -> None:
            self.text = text
            self.citations = citations
            self.n_retrieved = len(citations)

    def ask(self, question: str, *, top_k: int = 5) -> Any:
        return _FakeRAG._Answer(
            text="Hiến pháp 2013 quy định bình đẳng giới tại Điều 26.",
            citations=[_FakeRAG._Citation("Điều 26: Công dân nam, nữ bình đẳng về mọi mặt …")],
        )


def test_single_agent_answers_via_rag_tool() -> None:
    """Step 1: agent picks the RAG tool. Step 2: agent emits final answer
    using the tool's output. This is the user-explicit ask path:
    'answer questions based on files'."""
    rag = _FakeRAG()
    rag_tool = RAGTool(rag=rag, name="search_legal")

    llm = _ScriptedLLM(
        [
            # Step 1: tool call
            {
                "thought": "Need to look this up in the legal corpus.",
                "action": "tool_call",
                "tool_name": "search_legal",
                "tool_args": {"question": "Hiến pháp 2013 và bình đẳng giới"},
            },
            # Step 2: final answer using the tool result
            {
                "thought": "Tool returned the answer; compose final reply.",
                "action": "final",
                "final_answer": "Theo Hiến pháp 2013 Điều 26, công dân nam nữ bình đẳng.",
            },
        ]
    )

    agent = SingleAgent(name="legal_advisor", llm=llm, tools=(rag_tool,))
    result = agent.run("Hiến pháp 2013 nói gì về bình đẳng giới?")

    assert isinstance(result, AgentResult)
    assert "Điều 26" in result.output
    assert result.n_tool_calls == 1
    assert result.n_llm_calls == 2
    kinds = [e.kind for e in result.trace.events]
    assert "tool_call" in kinds
    assert "tool_result" in kinds
    assert "final" in kinds


def test_single_agent_takes_arithmetic_action() -> None:
    """The 'take actions' path: agent uses a tool to compute, then answers."""
    llm = _ScriptedLLM(
        [
            {
                "thought": "Need to compute the total with VAT.",
                "action": "tool_call",
                "tool_name": "python_eval",
                "tool_args": {"expr": "(1500000 * 1.1)"},
            },
            {
                "thought": "Got the value, return final.",
                "action": "final",
                "final_answer": "Tổng cộng sau VAT 10%: 1,650,000 VND.",
            },
        ]
    )
    agent = SingleAgent(name="invoice", llm=llm, tools=(PythonEvalTool(),))
    r = agent.run("Hãy tính tổng 1.500.000 VND sau VAT 10%.")
    assert "1,650,000" in r.output
    assert r.n_tool_calls == 1


def test_single_agent_recovers_from_tool_error() -> None:
    """Agent should keep going when a tool raises ToolError; the error
    is surfaced to the LLM in the transcript so it can self-correct."""
    rag = _FakeRAG()
    llm = _ScriptedLLM(
        [
            # First call: bad args — RAGTool will raise ToolError ("question required").
            {
                "thought": "try a malformed call",
                "action": "tool_call",
                "tool_name": "search_legal",
                "tool_args": {},  # missing 'question'
            },
            # Second call: corrected
            {
                "thought": "saw the error, retry with question",
                "action": "tool_call",
                "tool_name": "search_legal",
                "tool_args": {"question": "bình đẳng giới"},
            },
            {
                "thought": "got it",
                "action": "final",
                "final_answer": "Theo Hiến pháp Điều 26 …",
            },
        ]
    )
    agent = SingleAgent(name="r", llm=llm, tools=(RAGTool(rag=rag, name="search_legal"),))
    result = agent.run("...")
    assert result.n_tool_calls == 2  # both attempts counted
    err_event = next(
        e for e in result.trace.events if e.kind == "tool_result" and not e.payload.get("ok")
    )
    assert err_event.payload["error"]


def test_single_agent_step_budget() -> None:
    """If the LLM never returns 'final', the agent stops at max_steps."""
    looping = _ScriptedLLM(
        [
            {
                "thought": "loop forever",
                "action": "tool_call",
                "tool_name": "python_eval",
                "tool_args": {"expr": "1+1"},
            }
        ]
        * 50  # plenty of responses
    )
    agent = SingleAgent(name="x", llm=looping, tools=(PythonEvalTool(),), max_steps=3)
    r = agent.run("compute things")
    assert r.n_tool_calls == 3
    assert r.n_llm_calls == 3
    assert "max_steps" not in r.output  # output is the fallback string
    err_events = [e for e in r.trace.events if e.kind == "error"]
    assert any("max_steps" in e.payload.get("reason", "") for e in err_events)


def test_runtime_handles_unknown_tool_call_gracefully() -> None:
    """LLM picks a tool that doesn't exist → tool_result.error mentions it,
    agent can recover."""
    llm = _ScriptedLLM(
        [
            {
                "thought": "try ghost tool",
                "action": "tool_call",
                "tool_name": "ghost",
                "tool_args": {},
            },
            {
                "thought": "ok give up",
                "action": "final",
                "final_answer": "Không có công cụ phù hợp.",
            },
        ]
    )
    agent = SingleAgent(name="r", llm=llm, tools=(PythonEvalTool(),))
    r = agent.run("...")
    err = next(e for e in r.trace.events if e.kind == "tool_result" and not e.payload.get("ok"))
    assert "ghost" in err.payload["error"]


def test_runtime_handles_unparsable_response() -> None:
    """A garbled LLM response shouldn't crash the loop."""
    llm = _ScriptedLLM(
        [
            "this is not JSON at all",
            {"thought": "ok", "action": "final", "final_answer": "Đã thử lại."},
        ]
    )
    agent = SingleAgent(name="r", llm=llm, tools=(PythonEvalTool(),))
    r = agent.run("...")
    assert r.output == "Đã thử lại."
    parse_err = next(
        e
        for e in r.trace.events
        if e.kind == "error" and "unparsable" in e.payload.get("reason", "")
    )
    assert parse_err is not None


# ---------- ChainAgent ------------------------------------------------


def test_chain_agent_threads_outputs() -> None:
    llm = _ScriptedLLM(
        [
            "Bản tóm tắt: 3 điểm chính của tài liệu.",
            "Bản dịch sang tiếng Anh: 3 main points of the document.",
        ]
    )
    chain = ChainAgent(
        name="summarise_then_translate",
        llm=llm,
        steps=("Tóm tắt: {input}", "Dịch sang tiếng Anh: {previous}"),
    )
    r = chain.run("Hiến pháp 2013 …")
    assert "main points" in r.output
    assert r.n_llm_calls == 2


# ---------- RouteAgent ------------------------------------------------


def test_route_agent_dispatches_to_specialist() -> None:
    legal = SingleAgent(
        name="legal",
        llm=_ScriptedLLM(
            [{"thought": "x", "action": "final", "final_answer": "Câu trả lời pháp luật."}]
        ),
    )
    medical = SingleAgent(
        name="medical",
        llm=_ScriptedLLM(
            [{"thought": "x", "action": "final", "final_answer": "Câu trả lời y tế."}]
        ),
    )
    router_llm = _ScriptedLLM([{"label": "legal", "reason": "câu hỏi pháp luật"}])
    router = RouteAgent(
        name="router",
        llm=router_llm,
        routes={"legal": legal, "medical": medical},
        descriptions={"legal": "Pháp luật", "medical": "Y tế"},
    )
    r = router.run("Quy định bình đẳng giới ở đâu?")
    assert r.output == "Câu trả lời pháp luật."
    assert r.final_state["route"] == "legal"


def test_route_agent_uses_default_on_unknown_label() -> None:
    fallback = SingleAgent(
        name="fb",
        llm=_ScriptedLLM(
            [{"thought": "x", "action": "final", "final_answer": "Đã chuyển fallback."}]
        ),
    )
    router = RouteAgent(
        name="router",
        llm=_ScriptedLLM([{"label": "unknown", "reason": "?"}]),
        routes={"fallback": fallback},
        descriptions={"fallback": "Fallback"},
        default_route="fallback",
    )
    r = router.run("...")
    assert "fallback" in r.output


# ---------- ParallelAgent + VotingAgent -------------------------------


def test_parallel_agent_aggregates_outputs() -> None:
    a = SingleAgent(
        name="a", llm=_ScriptedLLM([{"thought": "", "action": "final", "final_answer": "Phần 1."}])
    )
    b = SingleAgent(
        name="b", llm=_ScriptedLLM([{"thought": "", "action": "final", "final_answer": "Phần 2."}])
    )
    p = ParallelAgent(name="p", sub_agents=(a, b))
    r = p.run("phân tích tài liệu")
    assert "Phần 1." in r.output
    assert "Phần 2." in r.output


def test_voting_agent_picks_majority() -> None:
    # 2/3 votes for "Yes", 1/3 for "No".
    class _ConstantAgent:
        name = "const"

        def __init__(self, ans: str) -> None:
            self._ans = ans

        def run(self, input: str, *, trace: Any = None) -> AgentResult:  # noqa: A002
            from nom.agents.protocol import Trace as _Trace

            t = trace or _Trace()
            t.emit("final", answer=self._ans)
            return AgentResult(output=self._ans, trace=t, n_llm_calls=1)

    # Build a sub-agent that returns deterministically; use a counter.
    answers = ["Yes", "Yes", "No"]

    class _ScriptedAgent:
        name = "scripted"
        _idx = 0
        _lock: Any = None

        def run(self, input: str, *, trace: Any = None) -> AgentResult:  # noqa: A002
            import threading

            from nom.agents.protocol import Trace as _Trace

            if self._lock is None:
                self._lock = threading.Lock()
            with self._lock:
                ans = answers[self._idx]
                self._idx += 1
            t = trace or _Trace()
            t.emit("final", answer=ans)
            return AgentResult(output=ans, trace=t, n_llm_calls=1)

    voter = VotingAgent(name="v", sub_agent=_ScriptedAgent(), n_samples=3, max_workers=1)
    r = voter.run("test")
    assert r.output == "Yes"
    assert r.final_state["votes"]["yes"] == 2


# ---------- OrchestratorWorkers ---------------------------------------


def test_orchestrator_decomposes_and_synthesises() -> None:
    legal = SingleAgent(
        name="legal",
        llm=_ScriptedLLM(
            [{"thought": "", "action": "final", "final_answer": "Khía cạnh pháp lý: …"}]
        ),
    )
    finance = SingleAgent(
        name="finance",
        llm=_ScriptedLLM(
            [{"thought": "", "action": "final", "final_answer": "Khía cạnh tài chính: …"}]
        ),
    )
    supervisor_llm = _ScriptedLLM(
        [
            {
                "subtasks": [
                    {"worker": "legal", "subtask": "Phân tích pháp lý của hợp đồng."},
                    {"worker": "finance", "subtask": "Phân tích tài chính của hợp đồng."},
                ]
            },
            "Tổng hợp: bao gồm cả pháp lý và tài chính.",
        ]
    )
    orch = OrchestratorWorkers(
        name="contract_review",
        llm=supervisor_llm,
        workers={"legal": legal, "finance": finance},
    )
    r = orch.run("Phân tích hợp đồng X")
    assert "Tổng hợp" in r.output
    assert len(r.final_state["worker_outputs"]) == 2


# ---------- EvaluatorOptimizer ----------------------------------------


def test_evaluator_optimizer_iterates_until_pass() -> None:
    gen = _ScriptedLLM(["Bản nháp 1 còn yếu.", "Bản nháp 2 đã sửa theo phản hồi."])
    judge = _ScriptedLLM(
        [
            {"verdict": "revise", "feedback": "Thiếu trích dẫn.", "score": 0.4},
            {"verdict": "pass", "feedback": "", "score": 0.9},
        ]
    )
    eo = EvaluatorOptimizer(
        name="critic_loop",
        generator_llm=gen,
        evaluator_llm=judge,
        generator_prompt="Viết bản tóm tắt cho: {input}",
        evaluator_prompt="Đánh giá bản tóm tắt cho: {input}",
        max_iters=3,
    )
    r = eo.run("Tài liệu X")
    assert "Bản nháp 2" in r.output
    assert r.final_state["iterations"] == 2


def test_evaluator_optimizer_caps_at_max_iters() -> None:
    gen = _ScriptedLLM(["d1", "d2", "d3", "d4"])
    judge = _ScriptedLLM(
        [
            {"verdict": "revise", "feedback": "f1", "score": 0.3},
            {"verdict": "revise", "feedback": "f2", "score": 0.4},
            {"verdict": "revise", "feedback": "f3", "score": 0.5},
        ]
    )
    eo = EvaluatorOptimizer(
        name="x",
        generator_llm=gen,
        evaluator_llm=judge,
        generator_prompt="g {input}",
        evaluator_prompt="e {input}",
        max_iters=3,
    )
    r = eo.run("...")
    assert r.final_state["exhausted"] is True
    assert r.output == "d3"  # last draft kept


# ---------- Trace shape -----------------------------------------------


def test_trace_records_event_sequence() -> None:
    llm = _ScriptedLLM([{"thought": "", "action": "final", "final_answer": "ok"}])
    agent = SingleAgent(name="x", llm=llm)
    r = agent.run("hi")
    kinds = [e.kind for e in r.trace.events]
    assert kinds[0] == "start"
    assert kinds[-1] == "end"
    assert "final" in kinds
