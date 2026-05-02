"""LLM-driven tool-loop runtime.

The mechanical bit shared by every pattern: call the LLM with a
serialised tool catalogue, parse a JSON action, dispatch it,
feed the result back, repeat until the LLM emits a ``final`` action
or a step-budget is exhausted.

The action protocol is explicit JSON, NOT vendor-specific function
calling. Reasons:

1. ``nom.llm.LLM`` is a 1-method Protocol — adding tool-call shape
   per provider doubles the API surface and re-introduces the
   "abstraction obscures the prompt" failure mode Anthropic warns
   about in *Building Effective Agents*.
2. Ollama / llama.cpp / OpenAI-compat endpoints all reliably emit
   structured JSON via ``schema=``. We use that.
3. JSON makes audit traces and replay trivial — no provider-specific
   tool-call ID translation.

The runtime emits every step into ``Trace``; if an ``AuditedLLM`` is
passed in (the default for production), each LLM ``complete`` call
also lands in the chain-signed compliance audit log.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nom.agents.protocol import Tool, ToolCall, ToolError, ToolResult, Trace

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = [
    "ACTION_SCHEMA",
    "ToolLoop",
    "render_tools_for_prompt",
    "system_prompt_for_tools",
]


# JSON-Schema for the LLM's per-step action. The model picks one of
# {tool_call, final}. We use ``oneOf`` so most JSON-mode-capable
# adapters route through their constrained-decoding path.
ACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "thought": {
            "type": "string",
            "description": "Brief reasoning for this step. One short sentence.",
        },
        "action": {
            "type": "string",
            "enum": ["tool_call", "final"],
            "description": (
                "Either invoke a tool ('tool_call') or stop and return the final answer ('final')."
            ),
        },
        "tool_name": {
            "type": "string",
            "description": "Name of the tool when action == 'tool_call'.",
        },
        "tool_args": {
            "type": "object",
            "description": "Arguments passed to the tool.",
        },
        "final_answer": {
            "type": "string",
            "description": "Final answer to the user when action == 'final'.",
        },
    },
    "required": ["thought", "action"],
}


def render_tools_for_prompt(tools: tuple[Tool, ...]) -> str:
    """Serialise a tool catalogue into a compact prompt block."""
    if not tools:
        return "(no tools available)"
    lines: list[str] = []
    for t in tools:
        lines.append(f"- {t.name}: {t.description}")
        if t.schema:
            lines.append(f"  args schema: {json.dumps(t.schema, ensure_ascii=False)}")
    return "\n".join(lines)


def system_prompt_for_tools(tools: tuple[Tool, ...]) -> str:
    """Standard system prompt prefix that explains the action protocol.

    Kept short — Anthropic's guide emphasises that explicit, simple
    prompts beat clever framework abstractions.
    """
    return (
        "Bạn là một AI agent có công cụ. Mỗi lượt, hãy quyết định:\n"
        "- gọi một công cụ (action='tool_call') với tool_name + tool_args, hoặc\n"
        "- trả lời cuối cùng (action='final') với final_answer.\n\n"
        "Trả về JSON đúng schema được yêu cầu, không text khác.\n\n"
        "Công cụ có sẵn:\n"
        f"{render_tools_for_prompt(tools)}\n\n"
        "Quy tắc: nếu cần thông tin từ tài liệu, dùng công cụ trước rồi mới "
        "trả lời. Đừng bịa thông tin. Nếu công cụ trả lỗi, đọc lỗi và thử "
        "cách khác hoặc dừng và báo cho người dùng."
    )


@dataclass
class ToolLoop:
    """Run an LLM ↔ tools loop until ``final`` or ``max_steps`` reached.

    The loop keeps a running transcript (``messages``) the LLM sees
    every step so it can chain across actions. We do NOT use vendor
    chat-message objects — the transcript is plain text, easy to
    audit, easy to replay.
    """

    llm: LLM
    tools: tuple[Tool, ...]
    max_steps: int = 8
    system_prompt: str | None = None

    def run(self, user_input: str, *, trace: Trace) -> tuple[str, dict[str, int]]:
        """Drive the loop until completion. Returns ``(final_answer, stats)``.

        ``stats`` is ``{"n_tool_calls": int, "n_llm_calls": int}``.
        """
        sys_prompt = self.system_prompt or system_prompt_for_tools(self.tools)
        transcript: list[str] = [f"[user] {user_input}"]
        n_tool = 0
        n_llm = 0

        for step in range(self.max_steps):
            prompt = (
                f"{sys_prompt}\n\n"
                f"=== Lịch sử ===\n" + "\n".join(transcript) + "\n\n=== Quyết định bước tiếp ==="
            )
            raw = self.llm.complete(prompt, schema=ACTION_SCHEMA, max_tokens=1024)
            n_llm += 1

            try:
                action = _parse_action(raw)
            except ValueError as exc:
                trace.emit("error", step=step, reason=f"unparsable: {exc}", raw=raw)
                # Feed the parse error back so the LLM can self-correct.
                transcript.append(f"[error] could not parse action: {exc}")
                continue

            trace.emit(
                "think",
                step=step,
                thought=action.get("thought", ""),
                action=action.get("action"),
            )

            if action["action"] == "final":
                answer = str(action.get("final_answer", "")).strip()
                trace.emit("final", step=step, answer=answer)
                return answer, {"n_tool_calls": n_tool, "n_llm_calls": n_llm}

            # action == "tool_call"
            tool_name = str(action.get("tool_name", ""))
            tool_args = dict(action.get("tool_args") or {})
            call = ToolCall(tool_name=tool_name, args=tool_args)
            trace.emit(
                "tool_call",
                step=step,
                call_id=call.call_id,
                tool=tool_name,
                args=tool_args,
            )
            result = self._dispatch(call)
            n_tool += 1
            trace.emit(
                "tool_result",
                step=step,
                call_id=call.call_id,
                ok=result.ok,
                output=_truncate_for_log(result.output),
                error=result.error,
            )
            transcript.append(
                f"[think] {action.get('thought', '')}\n"
                f"[tool_call:{tool_name}] args={json.dumps(tool_args, ensure_ascii=False)}\n"
                f"[tool_result] {_serialise_for_prompt(result)}"
            )

        # Step budget exhausted.
        trace.emit("error", reason="max_steps reached", max_steps=self.max_steps)
        return (
            "Đã hết ngân sách bước. Trả về kết quả tạm thời dựa trên thông tin đã thu thập.",
            {"n_tool_calls": n_tool, "n_llm_calls": n_llm},
        )

    def _dispatch(self, call: ToolCall) -> ToolResult:
        import time

        for tool in self.tools:
            if tool.name == call.tool_name:
                t0 = time.perf_counter()
                try:
                    out = tool.call(call.args)
                except ToolError as exc:
                    return ToolResult(
                        call_id=call.call_id,
                        ok=False,
                        output=None,
                        error=str(exc),
                        elapsed_ms=(time.perf_counter() - t0) * 1000,
                    )
                return ToolResult(
                    call_id=call.call_id,
                    ok=True,
                    output=out,
                    elapsed_ms=(time.perf_counter() - t0) * 1000,
                )
        return ToolResult(
            call_id=call.call_id,
            ok=False,
            output=None,
            error=f"unknown tool {call.tool_name!r}; available: {[t.name for t in self.tools]}",
        )


def _parse_action(raw: str) -> dict[str, Any]:
    """Tolerant JSON action parser.

    LLMs sometimes wrap JSON in markdown fences or emit trailing
    prose. We salvage the first balanced ``{…}`` substring.
    """
    raw = raw.strip()
    # Strip ```json fences if present.
    if raw.startswith("```"):
        lines = raw.splitlines()
        # drop opening fence
        lines = lines[1:]
        # drop closing fence
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Recover the first balanced object.
        start = raw.find("{")
        if start < 0:
            msg = f"no JSON object in {raw[:120]!r}"
            raise ValueError(msg) from None
        depth = 0
        for i in range(start, len(raw)):
            c = raw[i]
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    try:
                        data = json.loads(raw[start : i + 1])
                        break
                    except json.JSONDecodeError as exc:
                        raise ValueError(str(exc)) from exc
        else:
            msg = "unbalanced JSON"
            raise ValueError(msg)

    if not isinstance(data, dict):
        msg = f"expected JSON object, got {type(data).__name__}"
        raise ValueError(msg)
    if "action" not in data:
        msg = "action field missing"
        raise ValueError(msg)
    return data


def _serialise_for_prompt(result: ToolResult) -> str:
    """Compact representation of a tool result for the LLM's transcript."""
    if not result.ok:
        return f"ERROR: {result.error}"
    if isinstance(result.output, str):
        return result.output[:2000]
    try:
        return json.dumps(result.output, ensure_ascii=False)[:2000]
    except (TypeError, ValueError):
        return repr(result.output)[:2000]


def _truncate_for_log(output: Any, *, n: int = 400) -> Any:
    """Shorten tool output for trace events so logs stay readable."""
    if isinstance(output, str):
        return output if len(output) <= n else output[:n] + "…"
    return output
