"""Visual diff helper for goldens: SSIM plus a differing-pixel ratio (TEST_PLAN section 7).

A comparison fails when more than `max_pixel_ratio` of pixels differ by more than
`pixel_tolerance` in any channel, or when SSIM falls under `min_ssim`. On failure a diff image
is written under tests/visual/__diff__/ so CI can upload it.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

DEFAULT_MAX_PIXEL_RATIO = 0.001  # 0.1 percent of pixels
DEFAULT_PIXEL_TOLERANCE = 16
DEFAULT_MIN_SSIM = 0.995
DIFF_DIR = Path(__file__).resolve().parent / "__diff__"


@dataclass(frozen=True)
class CompareResult:
    ok: bool
    pixel_ratio: float
    ssim: float
    reason: str = ""


def _load(path_or_image: Path | Image.Image) -> np.ndarray:
    img = path_or_image if isinstance(path_or_image, Image.Image) else Image.open(path_or_image)
    return np.asarray(img.convert("RGB"), dtype=np.int16)


def compare(
    actual: Path | Image.Image,
    golden: Path | Image.Image,
    *,
    max_pixel_ratio: float = DEFAULT_MAX_PIXEL_RATIO,
    pixel_tolerance: int = DEFAULT_PIXEL_TOLERANCE,
    min_ssim: float = DEFAULT_MIN_SSIM,
    name: str = "diff",
) -> CompareResult:
    a, g = _load(actual), _load(golden)
    if a.shape != g.shape:
        return CompareResult(False, 1.0, 0.0, f"size differs: {a.shape} vs {g.shape}")
    differing = np.abs(a - g).max(axis=2) > pixel_tolerance
    ratio = float(differing.mean())
    gray_a = a.mean(axis=2)
    gray_g = g.mean(axis=2)
    ssim = float(structural_similarity(gray_a, gray_g, data_range=255.0))
    ok = ratio <= max_pixel_ratio and ssim >= min_ssim
    if not ok:
        DIFF_DIR.mkdir(parents=True, exist_ok=True)
        Image.fromarray((differing * 255).astype(np.uint8)).save(DIFF_DIR / f"{name}.png")
    reason = "" if ok else f"pixel ratio {ratio:.5f}, ssim {ssim:.4f}"
    return CompareResult(ok, ratio, ssim, reason)
