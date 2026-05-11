from PIL import Image, ImageFilter, ImageStat
import numpy as np
from loguru import logger

THUMBNAIL_MAX_PIXELS = 10_000  # 100×100

_EXIF_CAMERA_KEYS = ("Make", "Model")
_EXIF_DATE_KEYS = ("DateTimeOriginal", "DateTimeDigitized", "DateTime")


def check_resolution(file_path: str) -> tuple[bool, float]:
    """True if actual pixel count < 10 000 (thumbnail-sized)."""
    with Image.open(file_path) as img:
        w, h = img.size
    pixels = float(w * h)
    return pixels < THUMBNAIL_MAX_PIXELS, pixels


def check_exif(exif_raw: dict) -> tuple[bool, float]:
    """True if no camera make/model AND no capture datetime — likely an internet copy."""
    has_camera = any(exif_raw.get(k) for k in _EXIF_CAMERA_KEYS)
    has_date = any(exif_raw.get(k) for k in _EXIF_DATE_KEYS)
    return not (has_camera or has_date), 0.0


def check_brightness(file_path: str) -> tuple[bool, float]:
    """True if mean luminance < 30 (too dark) or > 220 (overexposed)."""
    with Image.open(file_path) as img:
        mean = ImageStat.Stat(img.convert("L")).mean[0]
        logger.debug(f"Brightness check: mean={mean:.2f}")
    return mean < 30.0 or mean > 220.0, round(mean, 2)


def check_edge_density(file_path: str) -> tuple[bool, float]:
    """True if < 2% of pixels are edges — flat/featureless image."""
    with Image.open(file_path) as img:
        img_small = img.convert("L").resize((512, 512))
        arr = np.array(img_small.filter(ImageFilter.FIND_EDGES))
    ratio = float((arr > 10).sum()) / arr.size
    logger.debug(f"Edge density check: ratio={ratio:.4f}")
    return ratio < 0.02, round(ratio, 4)


def check_blur(file_path: str) -> tuple[bool, float]:
    """True if Laplacian variance < 100 — image is blurry."""
    with Image.open(file_path) as img:
        img_small = img.convert("L").resize((512, 512))
        arr = np.array(img_small, dtype=np.float64)
    lap = (
        arr[:-2, 1:-1] + arr[2:, 1:-1] +
        arr[1:-1, :-2] + arr[1:-1, 2:] -
        4 * arr[1:-1, 1:-1]
    )
    variance = float(lap.var())
    logger.debug(f"Blur check: Laplacian variance={variance:.2f}")
    return variance < 100.0, round(variance, 2)


def check_entropy(file_path: str) -> tuple[bool, float]:
    with Image.open(file_path) as img:
        # Размываем перед анализом — убираем JPEG-шум
        img_small = img.convert("L").resize((512, 512)).filter(ImageFilter.GaussianBlur(radius=2))

    arr = np.array(img_small)
    patch_size = 64
    entropies = []

    for i in range(0, arr.shape[0] - patch_size, patch_size):
        for j in range(0, arr.shape[1] - patch_size, patch_size):
            patch = Image.fromarray(arr[i:i+patch_size, j:j+patch_size])
            entropies.append(patch.entropy())

    entropy = float(np.median(entropies))
    return entropy < 3.0, round(entropy, 4)


def compute_colorfulness(file_path: str) -> float:
    """Mean HSV saturation across all pixels, returned on a 0–255 scale."""
    with Image.open(file_path) as img:
        arr = np.array(img.convert("HSV").resize((256, 256)), dtype=np.float32)
    return round(float(arr[:, :, 1].mean()), 2)


def get_visual_metrics(file_path: str) -> dict:
    """Return all raw visual metric values without any garbage judgment."""
    with Image.open(file_path) as img:
        w, h = img.size
        gray = img.convert("L").resize((512, 512))
        gray_arr = np.array(gray, dtype=np.float64)
        small_rgb = img.convert("RGB").resize((256, 256))

    brightness = round(float(np.mean(gray_arr)), 2)

    lap = (
        gray_arr[:-2, 1:-1] + gray_arr[2:, 1:-1] +
        gray_arr[1:-1, :-2] + gray_arr[1:-1, 2:] -
        4 * gray_arr[1:-1, 1:-1]
    )
    blur_variance = round(float(lap.var()), 2)

    from PIL import ImageFilter
    edges = np.array(gray.filter(ImageFilter.FIND_EDGES))
    edge_density = round(float((edges > 10).sum()) / edges.size, 4)

    from PIL import ImageFilter as IF
    blurred = gray.filter(IF.GaussianBlur(radius=2))
    blurred_arr = np.array(blurred)
    patch_size = 64
    entropies = []
    for i in range(0, blurred_arr.shape[0] - patch_size, patch_size):
        for j in range(0, blurred_arr.shape[1] - patch_size, patch_size):
            entropies.append(Image.fromarray(blurred_arr[i:i+patch_size, j:j+patch_size]).entropy())
    entropy = round(float(np.median(entropies)), 4) if entropies else 0.0

    hsv_arr = np.array(Image.fromarray(np.array(small_rgb)).convert("HSV"), dtype=np.float32)
    colorfulness = round(float(hsv_arr[:, :, 1].mean()), 2)

    return {
        "width": w,
        "height": h,
        "resolution_mpx": round(w * h / 1_000_000, 3),
        "brightness": brightness,
        "blur_variance": blur_variance,
        "edge_density": edge_density,
        "entropy": entropy,
        "colorfulness": colorfulness,
    }


def check_screenshot(file_path: str) -> tuple[bool, float]:
    """True if > 45% of pixels fall in the top-10 colors of a 64-color quantization.
    Screenshots have large flat-color regions (menus, toolbars, backgrounds)."""
    with Image.open(file_path) as img:
        small = img.convert("RGB").resize((256, 256))
        quantized = small.quantize(colors=64)
    arr = np.array(quantized)
    counts = np.bincount(arr.flatten(), minlength=64)
    top10_sum = sum(sorted(counts.tolist(), reverse=True)[:10])
    score = float(top10_sum) / arr.size
    logger.debug(f"Screenshot check: score={score:.4f}")
    return score > 0.45, round(score, 4)
