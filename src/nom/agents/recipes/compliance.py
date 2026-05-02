"""``compliance_screener`` — PII-aware agent wrapper.

Wraps any inner agent so every incoming task is screened by a PII
detector + redactor BEFORE the LLM sees it. Useful when the inner
agent calls a cloud LLM (Claude, GPT) and the input might contain
CCCD / phone numbers / customer addresses you don't want sent
outside the firewall.

Architecture: thin pre-processor agent that delegates to ``inner``.
Not built as a tool wrapper because PII handling is an *operator*
concern, not an LLM-controlled one — we don't trust the LLM to
decide what to redact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nom.agents.protocol import Agent, AgentResult, Trace
from nom.platform import (
    MaskRedactor,
    PIIDetector,
    Redactor,
    RegexPIIDetector,
)

if TYPE_CHECKING:
    pass

__all__ = ["compliance_screener"]


@dataclass
class _ComplianceScreener:
    """Agent decorator that redacts PII from the input before delegating.

    The resulting ``AgentResult`` carries the inner agent's full trace
    plus screening events emitted by this decorator, so an inspector
    sees exactly what was redacted from each request.
    """

    inner: Agent
    detector: PIIDetector = field(default_factory=RegexPIIDetector)
    redactor: Redactor = field(default_factory=MaskRedactor)
    policy: str = "mask"
    fail_on_pii: bool = False
    name: str = "compliance_screener"

    def run(self, task: str, *, trace: Trace | None = None) -> AgentResult:
        if trace is None:
            trace = Trace()
        spans = self.detector.detect(task)
        if spans:
            kinds = sorted({s.kind for s in spans})
            trace.emit(
                "privacy.detect",
                agent=self.name,
                n_spans=len(spans),
                kinds=kinds,
            )
            if self.fail_on_pii:
                trace.emit(
                    "privacy.block",
                    agent=self.name,
                    reason="fail_on_pii=True",
                )
                trace.emit("end", agent=self.name, ok=False)
                return AgentResult(
                    output=(
                        "Yêu cầu bị từ chối: phát hiện thông tin cá nhân "
                        f"({', '.join(kinds)}). Vui lòng loại bỏ trước khi "
                        "gửi lại."
                    ),
                    trace=trace,
                    final_state={"blocked": True, "kinds": kinds},
                )
            redacted = self.redactor.redact(task, spans, policy=self.policy)
            trace.emit(
                "privacy.redact",
                agent=self.name,
                policy=self.policy,
                preview=redacted[:120],
            )
        else:
            redacted = task

        return self.inner.run(redacted, trace=trace)


def compliance_screener(
    *,
    inner: Agent,
    detector: PIIDetector | None = None,
    redactor: Redactor | None = None,
    policy: str = "mask",
    fail_on_pii: bool = False,
    name: str = "compliance_screener",
) -> Agent:
    """Wrap ``inner`` so every task is PII-screened before reaching it.

    Args:
        inner: the agent that does the real work — typically the
            output of one of the other recipes (``legal_qa``,
            ``vn_doc_analyser``, …) or a custom SingleAgent.
        detector: PII detector. Default: ``RegexPIIDetector`` from
            the OSS layer (covers email, phone, CCCD, MST, account
            numbers). EE deployments pass
            ``nom_ee.privacy.VNAdvancedPIIDetector`` for proper-name
            and address coverage.
        redactor: redactor implementation. Default: ``MaskRedactor``
            (replaces with ``[CCCD]`` / ``[EMAIL]`` placeholders).
            EE deployments can pass ``nom_ee.privacy.TokenizeRedactor``
            for round-trippable redaction.
        policy: ``"mask"`` / ``"hash"`` / ``"drop"`` for OSS redactor;
            ``"tokenize"`` for the EE redactor.
        fail_on_pii: when True, any detected PII causes the screener
            to short-circuit with a denial response — used in
            sectors where redaction isn't sufficient and the request
            must come back without PII (legal-discovery, regulated
            health). Default False (redact + continue).
        name: name surfaced in trace events.
    """
    return _ComplianceScreener(
        inner=inner,
        detector=detector or RegexPIIDetector(),
        redactor=redactor or MaskRedactor(),
        policy=policy,
        fail_on_pii=fail_on_pii,
        name=name,
    )
