"""Đ11.1 — "you are interacting with AI" disclosure helpers.

The law doesn't prescribe wording; it requires that the user
*recognize* they are talking to AI. The two strings here are
opinionated short-form notices in VN/EN. Use them verbatim, prepend
to a chat session, or render via :func:`interaction_notice` with the
system / model name substituted in.
"""

from __future__ import annotations

__all__ = [
    "AI_INTERACTION_NOTICE_EN",
    "AI_INTERACTION_NOTICE_VI",
    "interaction_notice",
]


AI_INTERACTION_NOTICE_VI = (
    "🤖 Bạn đang trao đổi với hệ thống trí tuệ nhân tạo. "
    "Câu trả lời do AI sinh ra có thể không chính xác hoàn toàn. "
    "Tuân thủ Luật 134/2025/QH15 Điều 11.1."
)


AI_INTERACTION_NOTICE_EN = (
    "🤖 You are interacting with an AI system. "
    "AI-generated responses may not be fully accurate. "
    "Per Vietnam AI Law 134/2025/QH15 Article 11.1."
)


def interaction_notice(
    *,
    system_name: str,
    language: str = "vi",
    model_label: str | None = None,
) -> str:
    """Render a customised notice that names the deployer's system.

    ``system_name`` is the deployer-facing brand (e.g.,
    "Trợ lý hợp đồng"). ``model_label`` is optional — set when you
    want to also surface the underlying model (e.g., "qwen3:8b").

    Languages: ``"vi"`` (default) and ``"en"``. Other values fall
    back to VN since the deployment context is Vietnam.
    """
    base = AI_INTERACTION_NOTICE_EN if language == "en" else AI_INTERACTION_NOTICE_VI
    parts = [f"[{system_name}]", base]
    if model_label is not None:
        suffix = f"(Model: {model_label})" if language == "en" else f"(Mô hình: {model_label})"
        parts.append(suffix)
    return " ".join(parts)
