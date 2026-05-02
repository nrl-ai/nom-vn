"""Transparency obligations — Luật 134/2025 Đ11.

Đ11.1 mandates that an AI system interacting directly with users be
designed and operated so users recognize they are talking to AI.
Đ11.2 mandates that AI-generated audio / images / video be marked
in a machine-readable format prescribed by Government. Đ11.3-4
extend this to deepfake / synthetic content of real persons or
events.

The implementing decree for the exact format is not yet published
(Đ11.6 says Government will detail). This module ships a stable
schema today (C2PA-aligned + a nom-sidecar JSON fallback); when the
official format publishes we add a translator without breaking the
public API.
"""

from __future__ import annotations

from nom.compliance.transparency.interaction import (
    AI_INTERACTION_NOTICE_EN,
    AI_INTERACTION_NOTICE_VI,
    interaction_notice,
)
from nom.compliance.transparency.provenance import (
    PROVENANCE_VERSION,
    ProvenanceManifest,
    mark_image,
    mark_text_html,
    write_sidecar,
)

__all__ = [
    "AI_INTERACTION_NOTICE_EN",
    "AI_INTERACTION_NOTICE_VI",
    "PROVENANCE_VERSION",
    "ProvenanceManifest",
    "interaction_notice",
    "mark_image",
    "mark_text_html",
    "write_sidecar",
]
