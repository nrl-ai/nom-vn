"""Sequential prompt chaining.

Pipe N prompts in order; each step's output becomes the next step's
task substitute (placeholder ``{previous}``). Useful when the task
decomposes cleanly into fixed subtasks (Anthropic's "prompt chaining"
pattern).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from nom.agents.protocol import AgentResult, Trace

if TYPE_CHECKING:
    from nom.llm.base import LLM

__all__ = ["ChainAgent"]


@dataclass
class ChainAgent:
    """Run ``steps`` in order, threading each step's output through.

    Each step is a prompt template — ``{input}`` is replaced with the
    initial task, ``{previous}`` with the previous step's output.
    """

    name: str
    llm: LLM
    steps: tuple[str, ...]
    max_tokens_per_step: int = 1024

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        if trace is None:
            trace = Trace()
        trace.emit("start", agent=self.name, n_steps=len(self.steps), task=task[:200])
        previous = task
        n_llm = 0
        for i, template in enumerate(self.steps):
            prompt = template.replace("{input}", task).replace("{previous}", previous)
            trace.emit("think", agent=self.name, step=i, prompt_preview=prompt[:200])
            previous = self.llm.complete(prompt, max_tokens=self.max_tokens_per_step)
            n_llm += 1
            trace.emit("step_output", agent=self.name, step=i, output_preview=previous[:200])
        trace.emit("final", agent=self.name, answer=previous[:200])
        trace.emit("end", agent=self.name, ok=True)
        return AgentResult(output=previous, trace=trace, n_llm_calls=n_llm)
