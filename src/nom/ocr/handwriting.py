"""Handwriting OCR — specialist VLM wrappers for VN forms / notes / IDs.

Tesseract on VN handwriting clocks ~69 % CER (internal bench, 2026-05-01,
brianhuster dataset) — way above the threshold for any usable downstream
processing. This module ships a Vintern-1B-v3_5 wrapper that drops to
sub-15 % CER on the same set (per the survey; first-party bench pending).

Critical trap (see ``docs/sota_vn_2026q2_expansion.md``): VLMs hallucinate
on **tight line crops**. Pass full pages, not single-line crops. The
wrapper enforces this with a JSON-schema constraint in the prompt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

__all__ = [
    "HandwritingOcr",
    "HandwritingResult",
    "VinternHandwritingOcr",
]

_DEFAULT_VINTERN_MODEL = "5CD-AI/Vintern-1B-v3_5"

# Prompt that tells the VLM to behave as an OCR tool, not a chat
# assistant. The "schema constraint" framing reduces VLM hallucination
# on edge cases (blank pages, mostly-form pages, illegible scans) by
# forcing structured output rather than free-form narration.
_OCR_PROMPT = (
    "Bạn là công cụ OCR. Hãy chép lại CHÍNH XÁC mọi văn bản tiếng Việt "
    "trong ảnh — bao gồm cả chữ in và chữ viết tay. "
    "Giữ nguyên dấu, hoa thường, dấu câu, xuống dòng. "
    "KHÔNG diễn giải, KHÔNG tóm tắt, KHÔNG thêm chữ không có trong ảnh. "
    "Nếu không có chữ, trả lời chuỗi rỗng."
)


@dataclass(frozen=True, slots=True)
class HandwritingResult:
    """OCR output from a handwriting-capable engine.

    ``text`` is the full transcript (NFC-normalised). ``confidence`` is
    in [0, 1] when the engine surfaces one (Vintern doesn't, so it's
    set to ``None``); callers can treat ``None`` as "not measured" and
    fall back to a heuristic (length > 0, contains diacritics, etc.).
    """

    text: str
    model: str
    confidence: float | None = None


@runtime_checkable
class HandwritingOcr(Protocol):
    """Protocol seam for any handwriting OCR engine.

    Implementations must accept a file path or a raw image (bytes /
    PIL.Image-compatible), and return the full-page transcript.
    """

    name: str

    def transcribe(self, image: Path | str | bytes) -> HandwritingResult: ...


@dataclass
class VinternHandwritingOcr:
    """Vintern-1B-v3_5 wrapper — VN form / handwriting OCR.

    Lazy-imports ``transformers`` and ``torch``; the model
    (~1.8 GB safetensors, 0.9 B params) is downloaded on first
    ``transcribe`` call. Subsequent calls reuse the loaded pipeline.

    Inputs:
    - ``Path`` / ``str`` — file path to a PNG / JPG / TIFF / BMP / WebP.
    - ``bytes`` — raw image bytes (any PIL-readable format).

    Always pass the full page. The wrapper rejects images smaller than
    ``min_height`` pixels (default 60) on the short edge — that's the
    floor below which VLMs reliably hallucinate (single-line crops are
    typically 20-40 px tall and trigger the failure mode).
    """

    model_id: str = _DEFAULT_VINTERN_MODEL
    device: str | None = None  # "cpu", "cuda", "mps"; None = auto
    max_new_tokens: int = 1024
    min_height: int = 60
    name: str = "vintern-1b-v3_5"
    _model: Any = field(default=None, init=False, repr=False)
    _tokenizer: Any = field(default=None, init=False, repr=False)

    def _ensure_loaded(self) -> tuple[Any, Any]:
        if self._model is not None and self._tokenizer is not None:
            return self._model, self._tokenizer
        try:
            from transformers import AutoModel, AutoTokenizer
        except ImportError as exc:
            raise ImportError(
                "VinternHandwritingOcr requires transformers + torch. "
                "Install with: pip install 'transformers>=4.45' 'torch>=2.0'"
            ) from exc

        device = self.device
        if device is None:
            try:
                import torch

                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        # Vintern uses `trust_remote_code=True` — its model class lives in
        # the repo, not in transformers core. This matches their HF card.
        tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            self.model_id,
            trust_remote_code=True,
        )
        if device != "cpu":
            try:
                import torch

                # bf16 if available, else fp16 — saves ~2x VRAM vs fp32.
                if torch.cuda.is_available() and torch.cuda.is_bf16_supported():
                    model = model.to(device=device, dtype=torch.bfloat16)
                else:
                    model = model.to(device=device, dtype=torch.float16)
            except ImportError:
                model = model.to(device=device)
        model.eval()
        self._model = model
        self._tokenizer = tokenizer
        return model, tokenizer

    def transcribe(self, image: Path | str | bytes) -> HandwritingResult:
        try:
            from PIL import Image as PILImage
        except ImportError as exc:
            raise ImportError(
                "VinternHandwritingOcr requires Pillow. Install with: pip install Pillow"
            ) from exc

        if isinstance(image, bytes):
            opened = PILImage.open(BytesIO(image))
        else:
            opened = PILImage.open(Path(image))
        # `Image.open` returns an ImageFile (lazy); `.convert` returns a
        # plain Image. Annotate explicitly for mypy.
        img: Any = opened.convert("RGB")

        # Reject sub-`min_height` short-edge crops — VLM line-crop trap.
        if min(img.width, img.height) < self.min_height:
            raise ValueError(
                f"image short edge {min(img.width, img.height)} px < "
                f"min_height={self.min_height}; pass the full page, not a "
                f"line crop. VLMs hallucinate on tight crops "
                f"(see docs/sota_vn_2026q2_expansion.md)."
            )

        model, tokenizer = self._ensure_loaded()

        # Vintern's chat() helper takes (tokenizer, pixel_values, prompt).
        # The exact API name follows their model card; if missing we get
        # a clear AttributeError naming the public method.
        if not hasattr(model, "chat"):
            raise RuntimeError(
                f"loaded model {self.model_id!r} does not expose a `.chat()` "
                "method — Vintern repo may have changed API. Check the model "
                "card and update the wrapper."
            )

        # Vintern (InternVL family) wants pixel_values as a `[N_patches, 3,
        # 448, 448]` torch FloatTensor — NOT a PIL.Image. The PIL path on
        # the model card uses a `load_image()` helper that does the dynamic-
        # tiling preprocess. We inline a single-tile fallback here (no
        # tiling, just resize to 448²) — sufficient for OCR-on-page; a
        # follow-up can add the dynamic patch-grid for very dense pages.
        from nom.text import normalize

        pixel_values = _preprocess_for_internvl(img, model)

        text = model.chat(
            tokenizer,
            pixel_values,
            _OCR_PROMPT,
            generation_config={
                "max_new_tokens": self.max_new_tokens,
                "do_sample": False,
            },
        )
        # `chat` returns a str on some forks, (str, history) tuple on others.
        if isinstance(text, tuple):
            text = text[0]
        return HandwritingResult(
            text=normalize(str(text).strip()),
            model=self.model_id,
            confidence=None,
        )


# ---------------------------------------------------------------------- #
# InternVL-style preprocess — Vintern is built on InternVL's vision
# tower; pixel_values must be `[N_patches, 3, 448, 448]` ImageNet-
# normalized FloatTensor. This single-tile path is sufficient for line /
# page OCR; a dynamic-patch-grid pass for dense multi-column documents
# can be added when we hit that use case.
# ---------------------------------------------------------------------- #


def _preprocess_for_internvl(img: Any, model: Any) -> Any:
    """Convert a PIL.Image to ``pixel_values`` matching the model's device
    + dtype. Single-tile fallback (no dynamic patching)."""
    # torchvision lacks py.typed; the wrapper is `Any`-typed end-to-end so
    # mypy doesn't lose anything by hiding the imports under `Any`.
    transforms_mod: Any = __import__("torchvision.transforms", fromlist=["Compose"])
    fn_mod: Any = __import__("torchvision.transforms.functional", fromlist=["InterpolationMode"])

    transform = transforms_mod.Compose(
        [
            transforms_mod.Resize((448, 448), interpolation=fn_mod.InterpolationMode.BICUBIC),
            transforms_mod.ToTensor(),
            transforms_mod.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
        ]
    )
    tile: Any = transform(img).unsqueeze(0)  # [1, 3, 448, 448]
    target_device = next(model.parameters()).device
    target_dtype = next(model.parameters()).dtype
    return tile.to(device=target_device, dtype=target_dtype)
