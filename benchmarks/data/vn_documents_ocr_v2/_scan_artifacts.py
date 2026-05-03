"""Comprehensive scan-artifact pipeline for synthetic-scan documents.

Layers eight passes onto a clean rendered page so it reads as a real
office-scanner output rather than a clean PIL render. Each component
has a conservative default tuned against real chinhphu.vn / hanoi.gov.vn
scans we already have in the corpus.

Pipeline order (matters):

  1. Skew          — rotate ±0.5-2.5° to simulate paper feed misalignment
  2. Vignette      — darken corners ~3-8% (scanner CCD cold spots)
  3. Color cast    — multiply RGB by (1.00, 0.99, 0.95) for mild yellow
                     paper age + (0.99, 0.99, 1.00) for scanner WB drift
  4. Paper grain   — additive gaussian noise sigma=3-5
  5. Banding       — faint horizontal periodic intensity (scanner roller),
                     amplitude +/- 2 luminance units, period ~50-90 rows
  6. Blur          — gaussian sigma=0.4-0.7 (scanner optics)
  7. Edge bleed    — narrow dark band at left/right edges (~1-3 px)
  8. JPEG          — quality 78-88 round-trip (typical scanner output)

Settings can be overridden per-component for variety across docs in
the corpus. The default ``ScanProfile.OFFICE_SCAN`` gives a moderate
2026-vintage scanner look.

Usage::

    from PIL import Image
    from _scan_artifacts import apply_scan_artifacts, ScanProfile

    img = Image.open("clean.png").convert("RGB")
    scanned = apply_scan_artifacts(img, profile=ScanProfile.OFFICE_SCAN, seed=42)
    scanned.save("scanned.jpg", quality=85)
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from enum import Enum

import numpy as np
from PIL import Image, ImageFilter


@dataclass(frozen=True, slots=True)
class ScanSettings:
    """All knobs for the scan-artifact pipeline."""

    # 1. skew
    skew_min_deg: float = 0.5
    skew_max_deg: float = 2.0
    # 2. vignette
    vignette_strength: float = 0.05  # 0 = off, 0.10 = strong
    # 3. color cast
    yellow_g_mul: float = 0.99  # green channel multiplier
    yellow_b_mul: float = 0.94  # blue channel multiplier (lower = more yellow)
    blue_r_mul: float = 0.99  # tiny red dampen for cool scanner WB
    # 4. paper grain
    grain_sigma: float = 4.0  # gaussian noise stdev
    # 5. banding
    banding_amplitude: float = 2.5
    banding_period_min: int = 50
    banding_period_max: int = 90
    # 6. blur
    blur_radius: float = 0.5
    # 7. edge bleed
    edge_bleed_px: int = 2
    edge_bleed_alpha: float = 0.35
    # 8. JPEG
    jpeg_quality: int = 84


class ScanProfile(Enum):
    """Named presets for different scan looks."""

    OFFICE_SCAN = "office_scan"  # default — modern office scanner
    OLD_PHOTOCOPY = "old_photocopy"  # higher noise, more skew, more JPEG
    CLEAN_DIGITAL = "clean_digital"  # minimal artifacts (~office laser printer)


_PROFILE_SETTINGS: dict[ScanProfile, ScanSettings] = {
    ScanProfile.OFFICE_SCAN: ScanSettings(),
    ScanProfile.OLD_PHOTOCOPY: ScanSettings(
        skew_min_deg=1.0,
        skew_max_deg=2.5,
        vignette_strength=0.10,
        yellow_b_mul=0.88,
        grain_sigma=7.0,
        banding_amplitude=4.5,
        blur_radius=0.8,
        edge_bleed_px=4,
        edge_bleed_alpha=0.5,
        jpeg_quality=72,
    ),
    ScanProfile.CLEAN_DIGITAL: ScanSettings(
        skew_min_deg=0.0,
        skew_max_deg=0.5,
        vignette_strength=0.02,
        yellow_b_mul=0.98,
        grain_sigma=1.5,
        banding_amplitude=0.5,
        blur_radius=0.2,
        edge_bleed_px=0,
        edge_bleed_alpha=0.0,
        jpeg_quality=92,
    ),
}


def _vignette(img: Image.Image, strength: float) -> Image.Image:
    """Multiply the corners by (1 - strength) on a radial falloff."""
    if strength <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    h, w = arr.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h / 2.0, w / 2.0
    r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    r_max = np.sqrt(cx**2 + cy**2)
    radial = (r / r_max) ** 2  # 0 at centre, 1 at corners
    falloff = 1.0 - strength * radial
    arr *= falloff[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), mode="RGB")


def _color_cast(img: Image.Image, *, g_mul: float, b_mul: float, r_mul: float) -> Image.Image:
    r, g, b = img.split()
    r = r.point(lambda p: max(0, min(255, int(p * r_mul))))
    g = g.point(lambda p: max(0, min(255, int(p * g_mul))))
    b = b.point(lambda p: max(0, min(255, int(p * b_mul))))
    return Image.merge("RGB", (r, g, b))


def _paper_grain(img: Image.Image, *, sigma: float, rng: np.random.Generator) -> Image.Image:
    if sigma <= 0:
        return img
    arr = np.asarray(img, dtype=np.int16)
    noise = rng.normal(0, sigma, arr.shape).astype(np.int16)
    return Image.fromarray(np.clip(arr + noise, 0, 255).astype("uint8"), mode="RGB")


def _banding(
    img: Image.Image,
    *,
    amplitude: float,
    period_min: int,
    period_max: int,
    rng: np.random.Generator,
) -> Image.Image:
    if amplitude <= 0:
        return img
    arr = np.asarray(img, dtype=np.int16)
    h = arr.shape[0]
    period = float(rng.integers(period_min, period_max + 1))
    phase = float(rng.uniform(0, 2 * np.pi))
    band = (amplitude * np.sin(2 * np.pi * np.arange(h) / period + phase)).astype(np.int16)
    arr += band[:, None, None]
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), mode="RGB")


def _edge_bleed(img: Image.Image, *, px: int, alpha: float) -> Image.Image:
    if px <= 0 or alpha <= 0:
        return img
    arr = np.asarray(img, dtype=np.float32)
    for x in range(px):
        weight = alpha * (1 - x / px)
        arr[:, x] *= 1 - weight  # left edge darken
        arr[:, -1 - x] *= 1 - weight  # right edge darken
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), mode="RGB")


def _jpeg_roundtrip(img: Image.Image, *, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    buf.seek(0)
    return Image.open(buf).convert("RGB").copy()


def apply_scan_artifacts(
    img: Image.Image,
    *,
    profile: ScanProfile = ScanProfile.OFFICE_SCAN,
    seed: int = 0,
    settings: ScanSettings | None = None,
) -> Image.Image:
    """Apply the eight-stage scan artifact pipeline to ``img``."""
    s = settings if settings is not None else _PROFILE_SETTINGS[profile]
    rng = np.random.default_rng(seed)

    # 1. Skew
    angle = float(rng.uniform(s.skew_min_deg, s.skew_max_deg))
    if rng.random() < 0.5:
        angle = -angle
    img = img.rotate(angle, resample=Image.BICUBIC, fillcolor=(255, 255, 255), expand=False)

    # 2. Vignette
    img = _vignette(img, strength=s.vignette_strength)

    # 3. Color cast (yellow + cool WB)
    img = _color_cast(img, g_mul=s.yellow_g_mul, b_mul=s.yellow_b_mul, r_mul=s.blue_r_mul)

    # 4. Paper grain
    img = _paper_grain(img, sigma=s.grain_sigma, rng=rng)

    # 5. Banding
    img = _banding(
        img,
        amplitude=s.banding_amplitude,
        period_min=s.banding_period_min,
        period_max=s.banding_period_max,
        rng=rng,
    )

    # 6. Blur (scanner optics)
    if s.blur_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=s.blur_radius))

    # 7. Edge bleed
    img = _edge_bleed(img, px=s.edge_bleed_px, alpha=s.edge_bleed_alpha)

    # 8. JPEG round-trip
    return _jpeg_roundtrip(img, quality=s.jpeg_quality)
