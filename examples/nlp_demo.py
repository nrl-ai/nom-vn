"""End-to-end demo of ``nom.nlp``.

Run from a checkout::

    python examples/nlp_demo.py

Exercises:

1. Language detection on mixed-language inputs
2. NER (regex baseline) on a news-style VN paragraph
3. Sentiment classification on three review-style snippets
4. A SingleAgent that uses NER + sentiment + language detection
   tools to produce a structured "document analysis" report

The agent uses a scripted LLM so the demo runs without any live
model. Swap in :class:`nom.llm.Ollama` or :class:`nom.llm.OpenAI`
(and a real API key) to see live multi-step reasoning.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from nom.agents import SingleAgent
from nom.agents.protocol import ToolError
from nom.nlp import (
    LexiconSentimentModel,
    RegexNERModel,
    detect_language,
)

# ---------- 1. language detection -----------------------------------


def demo_language_detection() -> None:
    print("\n=== 1. Language detection ===")
    samples = [
        ("Đây là một câu tiếng Việt.", "expected: vi"),
        ("This is plain English text.", "expected: en"),
        ("这是一段中文。", "expected: zh"),
        ("これは日本語です。", "expected: ja"),
        ("안녕하세요, 베트남.", "expected: ko"),
        ("!!! ??? ...", "expected: und"),
    ]
    for text, hint in samples:
        d = detect_language(text)
        print(f"  {text!r:60s} → {d.code}  conf={d.confidence:.2f}  ({hint})")


# ---------- 2. NER --------------------------------------------------


def demo_ner() -> None:
    print("\n=== 2. NER (regex baseline) ===")
    text = (
        "Vietcombank (VCB) thông báo gói tín dụng 1.500.000 VND cho hộ kinh "
        "doanh, áp dụng từ 02/05/2026 đến 31/12/2026. FPT và Viettel là "
        "đối tác triển khai."
    )
    spans = RegexNERModel().tag(text)
    print(f"  Text:\n    {text}\n")
    print("  Detected entities:")
    for s in spans:
        print(f"    [{s.label:5s}] {s.text:30s}  ({s.start}-{s.end})  conf={s.confidence:.2f}")


# ---------- 3. Sentiment --------------------------------------------


def demo_sentiment() -> None:
    print("\n=== 3. Sentiment (lexicon baseline) ===")
    samples = [
        "Sản phẩm này rất tuyệt vời, tôi rất hài lòng.",
        "Dịch vụ tệ quá, rất thất vọng và bực mình.",
        "Hôm nay trời mưa, tôi đi học.",
    ]
    model = LexiconSentimentModel()
    for text in samples:
        r = model.predict(text)
        print(f"  {r.label.value:8s}  score={r.score:.2f}  → {text!r}")


# ---------- 4. Agent that composes the NLP tools --------------------


class _NERTool:
    name = "extract_entities"
    description = (
        "Extract named entities (PER, ORG, LOC, MISC, DATE, MONEY) from a "
        "Vietnamese text. Returns a list of {label, text, start, end}."
    )
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def __init__(self) -> None:
        self._model = RegexNERModel()

    def call(self, args: dict[str, Any]) -> Any:
        text = args.get("text")
        if not isinstance(text, str) or not text:
            raise ToolError("`text` (str) is required")
        return [
            {"label": s.label, "text": s.text, "start": s.start, "end": s.end}
            for s in self._model.tag(text)
        ]


class _SentimentTool:
    name = "analyse_sentiment"
    description = (
        "Classify Vietnamese text as positive / neutral / negative. Returns {label, score}."
    )
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def __init__(self) -> None:
        self._model = LexiconSentimentModel()

    def call(self, args: dict[str, Any]) -> Any:
        text = args.get("text")
        if not isinstance(text, str) or not text:
            raise ToolError("`text` (str) is required")
        r = self._model.predict(text)
        return {"label": r.label.value, "score": r.score}


class _LanguageTool:
    name = "detect_language"
    description = "Detect the dominant language in text (vi/en/zh/ja/ko/und)."
    schema: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def call(self, args: dict[str, Any]) -> Any:
        text = args.get("text")
        if not isinstance(text, str) or not text:
            raise ToolError("`text` (str) is required")
        d = detect_language(text)
        return {"language": d.code, "confidence": d.confidence}


class _ScriptedLLM:
    """Scripted LLM that drives the agent through the three tools.

    Swap with :class:`nom.llm.Ollama("qwen3:8b")` for a live demo.
    """

    name = "scripted-demo"

    def __init__(self) -> None:
        self._script: list[dict[str, Any]] = [
            # Step 1: detect language so we know we're processing VN.
            {
                "thought": "First, confirm the input is Vietnamese.",
                "action": "tool_call",
                "tool_name": "detect_language",
                "tool_args": {"text": "{INPUT}"},
            },
            # Step 2: extract entities.
            {
                "thought": "Now extract entities so the user can see what's mentioned.",
                "action": "tool_call",
                "tool_name": "extract_entities",
                "tool_args": {"text": "{INPUT}"},
            },
            # Step 3: classify overall sentiment.
            {
                "thought": "Finally, classify the overall sentiment.",
                "action": "tool_call",
                "tool_name": "analyse_sentiment",
                "tool_args": {"text": "{INPUT}"},
            },
            # Step 4: synthesise a final report.
            {
                "thought": "Compose the final report from the gathered signals.",
                "action": "final",
                "final_answer": (
                    "Phân tích văn bản hoàn tất: ngôn ngữ đã xác định, "
                    "các thực thể đã trích xuất, cảm xúc đã phân loại. "
                    "(Demo agent — kết nối Ollama / vLLM để có phân tích "
                    "có ngữ cảnh.)"
                ),
            },
        ]
        self._user_input: str | None = None

    def complete(self, prompt: str, *, schema: Any | None = None, max_tokens: int = 2048) -> str:
        del max_tokens, schema
        if self._user_input is None:
            # Capture the original user input from the very first prompt
            # (it appears as the first ``[user] ...`` line).
            for line in prompt.splitlines():
                if line.startswith("[user] "):
                    self._user_input = line.removeprefix("[user] ")
                    break
        if not self._script:
            return json.dumps({"thought": "done", "action": "final", "final_answer": "(end)"})
        action = dict(self._script.pop(0))
        # Substitute the captured input wherever the script template
        # uses the {INPUT} placeholder.
        if self._user_input is not None and "tool_args" in action:
            args = dict(action["tool_args"])
            for k, v in args.items():
                if isinstance(v, str):
                    args[k] = v.replace("{INPUT}", self._user_input)
            action["tool_args"] = args
        return json.dumps(action, ensure_ascii=False)


def demo_nlp_agent() -> None:
    print("\n=== 4. SingleAgent composing NLP tools ===")
    text = "Khách hàng VCB rất hài lòng với gói tín dụng 1.500.000 VND, triển khai từ 02/05/2026."
    print(f"  Input: {text}\n")

    agent = SingleAgent(
        name="vn_doc_analyser",
        llm=_ScriptedLLM(),
        tools=(_LanguageTool(), _NERTool(), _SentimentTool()),
        max_steps=5,
    )
    result = agent.run(text)

    print(f"  Tool calls: {result.n_tool_calls}")
    print(f"  LLM calls:  {result.n_llm_calls}")
    print(f"  Output: {result.output}\n")
    print("  Trace events:")
    for ev in result.trace.events:
        if ev.kind == "tool_result":
            preview = str(ev.payload.get("output"))[:120]
            print(f"    [{ev.kind:11s}] {preview}")
        elif ev.kind == "tool_call":
            print(f"    [{ev.kind:11s}] {ev.payload.get('tool')}({ev.payload.get('args')})")
        elif ev.kind in {"start", "final", "end"}:
            note = ev.payload.get("answer") or ev.payload.get("agent") or ""
            print(f"    [{ev.kind:11s}] {note}")


def main() -> int:
    demo_language_detection()
    demo_ner()
    demo_sentiment()
    demo_nlp_agent()
    print("\nAll demos completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
