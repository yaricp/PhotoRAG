"""
Unit tests for quality_checks.py.
Each test creates a synthetic PIL image in memory — no real files needed.
"""

import numpy as np
from PIL import Image, ImageDraw

from src.quality_checks import (
    check_blur,
    check_brightness,
    check_edge_density,
    check_entropy,
    check_exif,
    check_resolution,
    check_screenshot,
)


def _save_tmp(img: Image.Image, tmp_path, name: str) -> str:
    path = str(tmp_path / name)
    img.save(path, format="JPEG")
    return path


# ── check_resolution ──────────────────────────────────────────────────────


def test_check_resolution_small_is_thumbnail(tmp_path):
    img = Image.new("RGB", (50, 50), color=(128, 128, 128))
    path = _save_tmp(img, tmp_path, "small.jpg")
    is_thumb, pixels = check_resolution(path)
    assert is_thumb is True
    assert pixels == 2500.0


def test_check_resolution_normal_not_thumbnail(tmp_path):
    img = Image.new("RGB", (800, 600), color=(128, 128, 128))
    path = _save_tmp(img, tmp_path, "normal.jpg")
    is_thumb, pixels = check_resolution(path)
    assert is_thumb is False
    assert pixels == 480_000.0


# ── check_exif ────────────────────────────────────────────────────────────


def test_check_exif_empty_dict_flagged():
    flagged, score = check_exif({})
    assert flagged is True
    assert score == 0.0


def test_check_exif_with_make_not_flagged():
    flagged, _ = check_exif({"Make": "Apple", "Model": "iPhone 14"})
    assert flagged is False


def test_check_exif_with_date_not_flagged():
    flagged, _ = check_exif({"DateTimeOriginal": "2023:01:01 12:00:00"})
    assert flagged is False


def test_check_exif_only_unrelated_keys_flagged():
    flagged, _ = check_exif({"Software": "Photoshop", "XResolution": 72})
    assert flagged is True


# ── check_brightness ──────────────────────────────────────────────────────


def test_check_brightness_dark_flagged(tmp_path):
    img = Image.new("RGB", (100, 100), color=(5, 5, 5))
    path = _save_tmp(img, tmp_path, "dark.jpg")
    flagged, mean = check_brightness(path)
    assert flagged is True
    assert mean < 30


def test_check_brightness_normal_not_flagged(tmp_path):
    img = Image.new("RGB", (100, 100), color=(128, 128, 128))
    path = _save_tmp(img, tmp_path, "normal.jpg")
    flagged, mean = check_brightness(path)
    assert flagged is False
    assert 30 <= mean <= 220


def test_check_brightness_overexposed_flagged(tmp_path):
    img = Image.new("RGB", (100, 100), color=(250, 250, 250))
    path = _save_tmp(img, tmp_path, "bright.jpg")
    flagged, mean = check_brightness(path)
    assert flagged is True
    assert mean > 220


# ── check_edge_density ────────────────────────────────────────────────────


def test_check_edge_density_flat_image_flagged(tmp_path):
    img = Image.new("RGB", (200, 200), color=(100, 100, 100))
    path = _save_tmp(img, tmp_path, "flat.jpg")
    flagged, ratio = check_edge_density(path)
    assert flagged is True
    assert ratio < 0.02


def test_check_edge_density_image_with_edges_not_flagged(tmp_path):
    img = Image.new("RGB", (200, 200), color=(200, 200, 200))
    draw = ImageDraw.Draw(img)
    for i in range(0, 200, 10):
        draw.line([(0, i), (200, i)], fill=(0, 0, 0), width=2)
        draw.line([(i, 0), (i, 200)], fill=(0, 0, 0), width=2)
    path = _save_tmp(img, tmp_path, "edges.jpg")
    flagged, ratio = check_edge_density(path)
    assert flagged is False
    assert ratio >= 0.02


# ── check_blur ────────────────────────────────────────────────────────────


def test_check_blur_uniform_image_is_blurry(tmp_path):
    img = Image.new("L", (100, 100), color=128)
    path = str(tmp_path / "uniform.png")
    img.save(path, format="PNG")
    flagged, variance = check_blur(path)
    assert flagged is True
    assert variance < 100.0


def test_check_blur_sharp_image_not_blurry(tmp_path):
    arr = np.zeros((100, 100), dtype=np.uint8)
    arr[::2, :] = 255  # alternating rows — maximum sharpness
    img = Image.fromarray(arr, mode="L")
    path = str(tmp_path / "sharp.png")
    img.save(path, format="PNG")
    flagged, variance = check_blur(path)
    assert flagged is False
    assert variance >= 100.0


# ── check_entropy ─────────────────────────────────────────────────────────


def test_check_entropy_uniform_image_low(tmp_path):
    img = Image.new("RGB", (100, 100), color=(100, 100, 100))
    path = _save_tmp(img, tmp_path, "uniform.jpg")
    flagged, entropy = check_entropy(path)
    assert flagged is True
    assert entropy < 3.0


def test_check_entropy_noisy_image_high(tmp_path):
    arr = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    path = _save_tmp(img, tmp_path, "noisy.jpg")
    flagged, entropy = check_entropy(path)
    assert flagged is False
    assert entropy >= 3.0


# ── check_screenshot ──────────────────────────────────────────────────────


def test_check_screenshot_ui_like_flagged(tmp_path):
    # UI-like: large solid-color blocks — very few distinct colors
    img = Image.new("RGB", (400, 300), color=(240, 240, 240))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 400, 40], fill=(70, 130, 180))  # title bar
    draw.rectangle([0, 260, 400, 300], fill=(200, 200, 200))  # status bar
    draw.rectangle([10, 50, 150, 80], fill=(100, 100, 200))  # button
    path = _save_tmp(img, tmp_path, "ui.jpg")
    flagged, score = check_screenshot(path)
    assert flagged is True
    assert score > 0.45


def test_check_screenshot_natural_photo_not_flagged(tmp_path):
    arr = np.random.randint(0, 256, (300, 400, 3), dtype=np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    path = _save_tmp(img, tmp_path, "natural.jpg")
    flagged, score = check_screenshot(path)
    assert flagged is False
