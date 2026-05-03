"""Vietnamese speech-to-text — Whisper / PhoWhisper wrappers.

Two production tiers behind a single ``SpeechToText`` Protocol:

- :class:`PhoWhisperSTT` — VinAI/PhoWhisper-large (BSD-3, .bin from VinAI).
  Strongest published WER on standard VN benchmarks (VIVOS 4.67 %,
  VLSP T1 13.75 %); best default for general VN audio. Trained on
  844 h covering 63 provinces, but per-region WER is unpublished —
  bench ViMD before claiming dialect coverage.
- :class:`WhisperSTT` — openai/whisper-large-v3 (MIT, safetensors).
  Multilingual zero-shot — better than PhoWhisper on VN↔EN
  code-switched business audio per ViMD findings; pick this when
  the input mixes Vietnamese with English tech / business terms.

The Protocol takes an audio file path or raw bytes, returns text +
optional segment timestamps. Both impls lazy-load transformers + torch
so the OSS install (no ML extras) keeps a small import surface.
"""

from nom.stt.whisper import (
    PhoWhisperSTT,
    SpeechToText,
    TranscriptionResult,
    TranscriptionSegment,
    WhisperSTT,
)

__all__ = [
    "PhoWhisperSTT",
    "SpeechToText",
    "TranscriptionResult",
    "TranscriptionSegment",
    "WhisperSTT",
]
