"""Orchestrator-workers pattern.

A supervisor LLM dynamically decomposes the task into sub-tasks,
dispatches each to a worker agent, and synthesises the results. The
key difference vs :class:`ParallelAgent`: subtasks are *generated*
from the task, not predetermined. Use when the structure of the
work isn't known until the model sees the request.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import TYPE_CHECKING

from nom.agents.protocol import Agent, AgentResult, Trace

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = ["OrchestratorWorkers"]


_PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "subtasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "worker": {"type": "string"},
                    "subtask": {"type": "string"},
                },
                "required": ["worker", "subtask"],
            },
            "minItems": 1,
        }
    },
    "required": ["subtasks"],
}


@dataclass
class OrchestratorWorkers:
    """Supervisor decomposes → workers execute → supervisor synthesises.

    ``workers`` maps role name → Agent. The supervisor LLM picks
    which workers to invoke and what subtask to give each one. After
    workers return, the supervisor produces the final synthesis.
    """

    name: str
    llm: LLM
    workers: Mapping[str, Agent]
    max_subtasks: int = 6
    max_workers: int = 4

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        if trace is None:
            trace = Trace()
        trace.emit("start", agent=self.name, available_workers=list(self.workers))

        plan = self._plan(task, trace)
        n_llm = 1

        if not plan:
            trace.emit("end", agent=self.name, ok=False, reason="no plan produced")
            return AgentResult(
                output="Không lập được kế hoạch xử lý.",
                trace=trace,
                n_llm_calls=n_llm,
            )

        # Run workers in parallel; preserve order for synthesis.
        worker_outputs: list[tuple[str, str, str]] = [None] * len(plan)  # type: ignore[list-item]
        n_tool = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {}
            for i, item in enumerate(plan):
                worker_name = item["worker"]
                if worker_name not in self.workers:
                    trace.emit(
                        "error",
                        agent=self.name,
                        reason=f"unknown worker {worker_name!r}",
                    )
                    worker_outputs[i] = (worker_name, item["subtask"], "(worker not registered)")
                    continue
                fut = ex.submit(self.workers[worker_name].run, item["subtask"])
                futures[fut] = (i, worker_name, item["subtask"])
            for fut in as_completed(futures):
                idx, worker_name, subtask = futures[fut]
                result = fut.result()
                worker_outputs[idx] = (worker_name, subtask, str(result.output))
                n_tool += result.n_tool_calls
                n_llm += result.n_llm_calls

        synthesis = self._synthesise(task, worker_outputs, trace)
        n_llm += 1

        trace.emit("end", agent=self.name, ok=True, n_subtasks=len(plan))
        return AgentResult(
            output=synthesis,
            trace=trace,
            n_tool_calls=n_tool,
            n_llm_calls=n_llm,
            final_state={"plan": plan, "worker_outputs": worker_outputs},
        )

    def _plan(self, task: str, trace: Trace) -> list[dict[str, str]]:
        worker_catalogue = "\n".join(f"- {name}" for name in self.workers)
        prompt = (
            "Phân rã yêu cầu sau thành các subtask, mỗi subtask giao cho một "
            "worker phù hợp. Trả JSON đúng schema.\n\n"
            f"Worker có sẵn:\n{worker_catalogue}\n\n"
            f"Yêu cầu: {input}\n\n"
            f"Tối đa {self.max_subtasks} subtask."
        )
        raw = self.llm.complete(prompt, schema=_PLAN_SCHEMA, max_tokens=1024)
        try:
            data = json.loads(_extract_json(raw))
        except (ValueError, json.JSONDecodeError) as exc:
            trace.emit("error", agent=self.name, reason=f"plan_unparseable: {exc}", raw=raw[:300])
            return []
        plan = list(data.get("subtasks", []))[: self.max_subtasks]
        trace.emit("think", agent=self.name, plan=plan)
        return plan

    def _synthesise(
        self,
        task: str,
        worker_outputs: list[tuple[str, str, str]],
        trace: Trace,
    ) -> str:
        joined = "\n\n".join(
            f"### {worker} → {subtask}\n{output}" for worker, subtask, output in worker_outputs
        )
        prompt = (
            "Tổng hợp các kết quả worker dưới đây thành một câu trả lời thống "
            "nhất cho yêu cầu gốc của người dùng.\n\n"
            f"Yêu cầu gốc: {input}\n\n"
            f"Kết quả worker:\n{joined}\n\n"
            "Trả lời cuối cùng:"
        )
        synthesis = self.llm.complete(prompt, max_tokens=1500)
        trace.emit("final", agent=self.name, answer_preview=synthesis[:200])
        return synthesis


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
