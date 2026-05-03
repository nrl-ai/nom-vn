"""Whisper-family speech-to-text — VN PhoWhisper + multilingual fallback.

Two wrappers behind a Protocol:

- :class:`PhoWhisperSTT` — ``VinAI/PhoWhisper-large`` default. Strongest
  published WER on standard VN benchmarks (VIVOS 4.67 %, VLSP T1 13.75 %).
  Trained on 844 h Vietnamese covering 63 provinces. Per-region WER is
  NOT published despite the broad coverage claim — bench against ViMD
  splits before asserting dialect coverage in production claims.
- :class:`WhisperSTT` — ``openai/whisper-large-v3`` for code-switched
  audio. ViMD-based survey shows large-v3 zero-shot beats PhoWhisper on
  VN↔EN business audio (mixed tech / management / acronym vocab).

Both use the standard HF ``transformers`` ``automatic-speech-recognition``
pipeline. NFC-normalise the output before return so callers get the
same form the rest of nom-vn expects.

Audio preprocessing notes:

- Long inputs are auto-chunked at 30 s (Whisper's native context). Set
  ``chunk_length_s`` to override.
- Mono channel + 16 kHz sample rate is what the model expects; pass
  ``return_timestamps=True`` to get word-level offsets back.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "PhoWhisperSTT",
    "SpeechToText",
    "TranscriptionResult",
    "TranscriptionSegment",
    "WhisperSTT",
]


@dataclass(frozen=True, slots=True)
class TranscriptionSegment:
    """One Whisper-emitted segment with character-grain offsets."""

    start: float
    end: float
    text: str


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """STT output. ``segments`` is ``None`` when the caller didn't request
    word-level timestamps (cheaper inference path)."""

    text: str
    model: str
    language: str | None = None
    segments: tuple[TranscriptionSegment, ...] | None = None


@runtime_checkable
class SpeechToText(Protocol):
    """Protocol seam for any STT engine.

    ``transcribe`` accepts a file path or raw audio bytes (any format
    ``transformers``/``ffmpeg`` can decode — wav, mp3, flac, m4a, ogg).
    """

    name: str

    def transcribe(
        self,
        audio: Path | str | bytes,
        *,
        language: str | None = None,
        return_timestamps: bool = False,
    ) -> TranscriptionResult: ...


def _load_pipeline(model_id: str, device: str | None) -> Any:
    """Build an HF asr pipeline; shared across PhoWhisper + Whisper-v3."""
    try:
        from transformers import pipeline
    except ImportError as exc:
        raise ImportError(
            "Whisper-family STT requires transformers + torch + librosa. "
            "Install with: pip install 'nom-vn[stt]' "
            "(brings transformers + torch + librosa + soundfile)."
        ) from exc

    if device is None:
        try:
            import torch

            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        except ImportError:
            device = "cpu"

    return pipeline(
        "automatic-speech-recognition",
        model=model_id,
        device=device,
        chunk_length_s=30,
    )


def _audio_input(audio: Path | str | bytes) -> Any:
    """Normalise audio input to something the HF pipeline accepts.

    Bytes get materialised to a temporary BytesIO; paths pass through.
    The pipeline does its own decoding via ``librosa`` / ``soundfile``;
    we don't need to read samples ourselves.
    """
    if isinstance(audio, bytes):
        return BytesIO(audio)
    return str(Path(audio))


def _coerce_text(raw_text: str) -> str:
    from nom.text import normalize

    return normalize(raw_text.strip())


def _build_segments(chunks: Any) -> tuple[TranscriptionSegment, ...] | None:
    """HF Whisper returns chunks as a list of {timestamp: (start, end), text}.

    Some forks emit ``timestamp`` as ``[start, end]``, others as a tuple.
    Tolerate both; skip rows where the timestamp couldn't be aligned
    (rare on short inputs, common on Whisper hallucinations near silence).
    """
    if not chunks:
        return None
    out: list[TranscriptionSegment] = []
    for c in chunks:
        ts = c.get("timestamp")
        if not ts or len(ts) != 2:
            continue
        start, end = ts
        if start is None or end is None:
            continue
        out.append(
            TranscriptionSegment(
                start=float(start), end=float(end), text=str(c.get("text", "")).strip()
            )
        )
    return tuple(out) if out else None


@dataclass
class PhoWhisperSTT:
    """PhoWhisper-large wrapper — VN-tuned default.

    Defaults to ``vinai/PhoWhisper-large`` (BSD-3, .bin pickled — VinAI
    is a recognised major lab, see project file-format trust ladder).
    Override ``model_id`` for the smaller ``PhoWhisper-medium`` /
    ``PhoWhisper-small`` tiers when latency matters more than absolute WER.
    """

    model_id: str = "vinai/PhoWhisper-large"
    device: str | None = None
    name: str = "phowhisper-large"
    _pipeline: Any = field(default=None, init=False, repr=False)

    def transcribe(
        self,
        audio: Path | str | bytes,
        *,
        language: str | None = None,
        return_timestamps: bool = False,
    ) -> TranscriptionResult:
        if self._pipeline is None:
            self._pipeline = _load_pipeline(self.model_id, self.device)

        # PhoWhisper is VN-only by training; ``language`` is ignored
        # (forced to "vi" by the model's generation_config). We accept
        # the kwarg for Protocol parity with multilingual Whisper.
        result = self._pipeline(
            _audio_input(audio),
            return_timestamps=return_timestamps,
        )
        text = _coerce_text(str(result.get("text", "")))
        segments = _build_segments(result.get("chunks")) if return_timestamps else None
        return TranscriptionResult(
            text=text,
            model=self.model_id,
            language="vi",
            segments=segments,
        )


@dataclass
class WhisperSTT:
    """openai/whisper-large-v3 wrapper — multilingual code-switch fallback.

    Use this on audio that mixes Vietnamese with English (business
    meetings, tech podcasts, dev podcasts) — survey finding: large-v3
    zero-shot beats PhoWhisper on VN↔EN code-switched audio.
    """

    model_id: str = "openai/whisper-large-v3"
    device: str | None = None
    name: str = "whisper-large-v3"
    _pipeline: Any = field(default=None, init=False, repr=False)

    def transcribe(
        self,
        audio: Path | str | bytes,
        *,
        language: str | None = None,
        return_timestamps: bool = False,
    ) -> TranscriptionResult:
        if self._pipeline is None:
            self._pipeline = _load_pipeline(self.model_id, self.device)

        # Whisper-large-v3 supports ``generate_kwargs={"language": "vi"}``
        # to force a target language — useful when input is mostly VN but
        # the model auto-detects EN for short clips. Pipeline requires
        # the kwarg be omitted (NOT passed as None) when empty — passing
        # ``None`` triggers ``TypeError: 'NoneType' object is not iterable``
        # in transformers' _sanitize_parameters.
        pipe_kwargs: dict[str, Any] = {"return_timestamps": return_timestamps}
        if language:
            pipe_kwargs["generate_kwargs"] = {"language": language}

        result = self._pipeline(_audio_input(audio), **pipe_kwargs)
        text = _coerce_text(str(result.get("text", "")))
        segments = _build_segments(result.get("chunks")) if return_timestamps else None
        return TranscriptionResult(
            text=text,
            model=self.model_id,
            language=language,
            segments=segments,
        )
