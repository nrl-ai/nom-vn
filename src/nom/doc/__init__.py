"""Document extraction — PDF/scan → structured JSON.

This module is a stub in v0.0.1. The real implementation ships with v0.1.
The signatures here are stable preview API — track at https://nrl.ai/nom.

Public surface:
    extract              — top-level convenience function
    Pipeline, Stage      — composable pipeline primitives
    Load, Parse, OCR,    — default stages (placeholders in v0.0.1)
    Normalize, Extract,
    Validate
"""

from nom.doc.extract import extract
from nom.doc.pipeline import Context, Pipeline, Stage, default_pipeline
from nom.doc.stages import OCR, Extract, Load, Normalize, Parse, Validate

__all__ = [
    "OCR",
    "Context",
    "Extract",
    "Load",
    "Normalize",
    "Parse",
    "Pipeline",
    "Stage",
    "Validate",
    "default_pipeline",
    "extract",
]
