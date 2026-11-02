"""S0-T05: the visual diff helper used by every golden test."""

from PIL import Image, ImageDraw

from tests.visual.compare import compare


def _glyph(offset: int = 0) -> Image.Image:
    img = Image.new("RGB", (200, 120), "white")
    draw = ImageDraw.Draw(img)
    draw.rectangle((40 + offset, 30, 160 + offset, 90), outline="black", width=3)
    draw.line((60 + offset, 60, 140 + offset, 60), fill="black", width=3)
    return img


def test_visual_compare_identical_images_pass() -> None:
    result = compare(_glyph(), _glyph())
    assert result.ok
    assert result.pixel_ratio == 0.0


def test_visual_compare_over_threshold_fails() -> None:
    noisy = _glyph()
    ImageDraw.Draw(noisy).rectangle((0, 0, 30, 30), fill="red")
    result = compare(noisy, _glyph(), name="over-threshold")
    assert not result.ok
    assert result.pixel_ratio > 0.001


def test_visual_compare_ssim_detects_shifted_glyph() -> None:
    result = compare(_glyph(1), _glyph(), name="shifted")
    assert not result.ok


def test_visual_compare_size_mismatch_fails() -> None:
    result = compare(Image.new("RGB", (10, 10)), Image.new("RGB", (11, 10)))
    assert not result.ok
    assert "size" in result.reason
