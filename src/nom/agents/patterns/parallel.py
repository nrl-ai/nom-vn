"""Parallel patterns: sectioning + voting.

- :class:`ParallelAgent` (sectioning) — run N independent sub-agents
  on disjoint subtasks and aggregate their outputs.
- :class:`VotingAgent` — run the same prompt N times and aggregate
  by majority / consensus (Anthropic's "voting" variant).

Concurrency: agents run on a thread pool. Each sub-agent gets its
own ``Trace``; the parent trace records aggregate timing only so
the log doesn't drown in interleaved sub-events.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Hashable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from nom.agents.protocol import Agent, AgentResult, Trace

__all__ = ["ParallelAgent", "VotingAgent"]


@dataclass
class ParallelAgent:
    """Run ``sub_agents`` on disjoint inputs in parallel; aggregate.

    ``map_fn`` (when provided) builds a per-sub task from the parent
    task — e.g., split a long doc into sections, one per worker.
    ``reduce_fn`` (when provided) combines outputs; default joins
    with newlines.
    """

    name: str
    sub_agents: tuple[Agent, ...]
    map_fn: Callable[[str], tuple[str, ...]] | None = None
    reduce_fn: Callable[[tuple[str, ...]], str] | None = None
    max_workers: int = 4

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        if trace is None:
            trace = Trace()
        trace.emit("start", agent=self.name, n_workers=len(self.sub_agents))

        sub_inputs: tuple[str, ...]
        if self.map_fn is not None:
            sub_inputs = tuple(self.map_fn(task))
        else:
            sub_inputs = (task,) * len(self.sub_agents)
        if len(sub_inputs) != len(self.sub_agents):
            msg = (
                f"map_fn returned {len(sub_inputs)} inputs but there are "
                f"{len(self.sub_agents)} sub-agents"
            )
            raise ValueError(msg)

        results: list[AgentResult | None] = [None] * len(self.sub_agents)
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {
                ex.submit(agent.run, sub_inputs[i]): i for i, agent in enumerate(self.sub_agents)
            }
            for fut in as_completed(futures):
                idx = futures[fut]
                results[idx] = fut.result()

        completed = [r for r in results if r is not None]
        outputs = tuple(r.output if isinstance(r.output, str) else str(r.output) for r in completed)
        aggregate = self.reduce_fn(outputs) if self.reduce_fn is not None else "\n\n".join(outputs)

        n_tool = sum(r.n_tool_calls for r in completed)
        n_llm = sum(r.n_llm_calls for r in completed)
        trace.emit("final", agent=self.name, n_outputs=len(outputs))
        trace.emit("end", agent=self.name, ok=True)
        return AgentResult(
            output=aggregate,
            trace=trace,
            n_tool_calls=n_tool,
            n_llm_calls=n_llm,
            final_state={"sub_outputs": outputs},
        )


@dataclass
class VotingAgent:
    """Run the SAME sub-agent N times; majority-vote over outputs.

    Useful when correctness depends on consistency (e.g., "is this
    contract risky? yes/no") and a single sample is too noisy.
    Outputs are normalised via ``key_fn`` before voting; default uses
    the trimmed lower-case string.
    """

    name: str
    sub_agent: Agent
    n_samples: int = 3
    key_fn: Callable[[str], Hashable] | None = None
    max_workers: int = 4

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        if trace is None:
            trace = Trace()
        trace.emit("start", agent=self.name, n_samples=self.n_samples)

        results: list[AgentResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = [ex.submit(self.sub_agent.run, task) for _ in range(self.n_samples)]
            for fut in as_completed(futures):
                results.append(fut.result())

        outputs = [r.output if isinstance(r.output, str) else str(r.output) for r in results]
        keys = [self._key(o) for o in outputs]
        counts: Counter[Hashable] = Counter(keys)
        winning_key, votes = counts.most_common(1)[0]
        # Pick a representative output that maps to the winning key.
        winner = next(o for o, k in zip(outputs, keys, strict=True) if k == winning_key)

        trace.emit(
            "final",
            agent=self.name,
            winning_votes=votes,
            distribution=dict(counts),
        )
        trace.emit("end", agent=self.name, ok=True)
        return AgentResult(
            output=winner,
            trace=trace,
            n_tool_calls=sum(r.n_tool_calls for r in results),
            n_llm_calls=sum(r.n_llm_calls for r in results),
            final_state={"votes": dict(counts)},
        )

    def _key(self, output: str) -> Hashable:
        if self.key_fn is not None:
            return self.key_fn(output)
        return output.strip().lower()
