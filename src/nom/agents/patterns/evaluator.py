"""Evaluator-optimizer pattern: generator + critic loop.

Generator produces a draft. Critic scores it (pass / revise) with
feedback. If revise: feed feedback back to generator, repeat. Bounds
total iterations so a stubborn critic doesn't burn tokens forever.

Use when there are clear evaluation criteria and iterative
refinement provides measurable value (Anthropic).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nom.agents.protocol import AgentResult, Trace

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = ["EvaluatorOptimizer"]


_VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["pass", "revise"]},
        "feedback": {"type": "string"},
        "score": {"type": "number"},
    },
    "required": ["verdict"],
}


@dataclass
class EvaluatorOptimizer:
    """Generator-critic loop with bounded iterations.

    Two LLMs (or two roles on the same LLM): the generator drafts an
    answer; the evaluator returns ``pass`` or ``revise`` with
    feedback. On ``revise``, the feedback is appended to the next
    generator prompt. Loop ends on ``pass`` or when ``max_iters`` is
    reached.
    """

    name: str
    generator_llm: LLM
    evaluator_llm: LLM
    generator_prompt: str
    evaluator_prompt: str
    max_iters: int = 3
    accept_score: float = 0.0

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        if trace is None:
            trace = Trace()
        trace.emit("start", agent=self.name)

        feedback: str = ""
        draft: str = ""
        n_llm = 0
        for it in range(self.max_iters):
            gen_prompt = self.generator_prompt.replace("{input}", task)
            if feedback:
                gen_prompt += (
                    f"\n\nBản nháp trước:\n{draft}\n\n"
                    f"Phản hồi của reviewer cần xử lý:\n{feedback}\n\n"
                    "Viết lại tốt hơn theo phản hồi:"
                )
            draft = self.generator_llm.complete(gen_prompt, max_tokens=1500)
            n_llm += 1
            trace.emit("step_output", agent=self.name, iteration=it, draft=draft[:300])

            eval_prompt = (
                self.evaluator_prompt.replace("{input}", task) + f"\n\nBản nháp:\n{draft}\n\n"
                'Trả JSON: {"verdict": "pass" | "revise", '
                '"feedback": "<điểm cần sửa nếu revise>", '
                '"score": <0-1>}.'
            )
            raw = self.evaluator_llm.complete(eval_prompt, schema=_VERDICT_SCHEMA, max_tokens=400)
            n_llm += 1
            try:
                verdict = json.loads(_extract_json(raw))
            except (ValueError, json.JSONDecodeError):
                verdict = {"verdict": "pass"}
            trace.emit(
                "think",
                agent=self.name,
                iteration=it,
                verdict=verdict.get("verdict"),
                score=verdict.get("score"),
                feedback=str(verdict.get("feedback", ""))[:200],
            )

            score = float(verdict.get("score") or 0.0)
            if verdict.get("verdict") == "pass" or score >= self.accept_score > 0:
                trace.emit("final", agent=self.name, iterations_used=it + 1)
                trace.emit("end", agent=self.name, ok=True)
                return AgentResult(
                    output=draft,
                    trace=trace,
                    n_llm_calls=n_llm,
                    final_state={"iterations": it + 1, "score": score},
                )
            feedback = str(verdict.get("feedback", ""))

        trace.emit(
            "final",
            agent=self.name,
            iterations_used=self.max_iters,
            note="max_iters reached",
        )
        trace.emit("end", agent=self.name, ok=True)
        return AgentResult(
            output=draft,
            trace=trace,
            n_llm_calls=n_llm,
            final_state={"iterations": self.max_iters, "exhausted": True},
        )


def _extract_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
    start = raw.find("{")
    if start < 0:
        return raw
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return raw[start:]
