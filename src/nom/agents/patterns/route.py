"""Routing pattern: classify, then dispatch to a specialist.

The router LLM picks one of N labels; the corresponding specialist
agent handles the task. Per Anthropic, this gives "separation of
concerns and more specialised prompts" — a customer-service router
sends refunds to the refunds specialist, technical questions to a
RAG-grounded agent, etc.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nom.agents.protocol import Agent, AgentResult, Trace

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = ["RouteAgent"]


@dataclass
class RouteAgent:
    """Classify task → dispatch to one of ``routes``.

    ``routes`` maps label → :class:`Agent`. ``descriptions`` (same
    keys) explains each route to the classifier LLM. If the LLM
    picks an unknown label or the ``default_route`` is set, that
    fallback runs; otherwise an error event is emitted.
    """

    name: str
    llm: LLM
    routes: Mapping[str, Agent]
    descriptions: Mapping[str, str]
    default_route: str | None = None

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        if trace is None:
            trace = Trace()
        trace.emit("start", agent=self.name, task=task[:200])

        labels = list(self.routes)
        catalogue = "\n".join(
            f"- {label}: {self.descriptions.get(label, '(no description)')}" for label in labels
        )
        prompt = (
            "Phân loại yêu cầu sau vào một trong các nhãn dưới đây.\n"
            'Trả về JSON: {"label": "<tên nhãn>", "reason": "<lý do ngắn>"}.\n\n'
            f"Nhãn:\n{catalogue}\n\n"
            f"Yêu cầu: {input}"
        )
        schema = {
            "type": "object",
            "properties": {
                "label": {"type": "string", "enum": labels},
                "reason": {"type": "string"},
            },
            "required": ["label"],
        }
        raw = self.llm.complete(prompt, schema=schema, max_tokens=200)
        try:
            decision = json.loads(_extract_json(raw))
        except (ValueError, json.JSONDecodeError):
            trace.emit("error", agent=self.name, reason="router_unparseable", raw=raw[:200])
            decision = {"label": self.default_route or labels[0]}

        label = str(decision.get("label", ""))
        if label not in self.routes:
            if self.default_route and self.default_route in self.routes:
                trace.emit(
                    "think",
                    agent=self.name,
                    note=f"unknown label {label!r}; using default {self.default_route!r}",
                )
                label = self.default_route
            else:
                trace.emit(
                    "error",
                    agent=self.name,
                    reason=f"unknown label {label!r} and no default",
                )
                trace.emit("end", agent=self.name, ok=False)
                return AgentResult(
                    output="Không phân loại được yêu cầu.",
                    trace=trace,
                    n_llm_calls=1,
                )

        trace.emit(
            "think",
            agent=self.name,
            label=label,
            reason=decision.get("reason", ""),
        )
        sub_result = self.routes[label].run(task, trace=trace)
        trace.emit("end", agent=self.name, ok=True, route=label)
        return AgentResult(
            output=sub_result.output,
            trace=trace,
            n_tool_calls=sub_result.n_tool_calls,
            n_llm_calls=sub_result.n_llm_calls + 1,
            final_state={"route": label},
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
