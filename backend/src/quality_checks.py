from PIL import Image, ImageFilter, ImageStat
import numpy as np

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
    return mean < 30.0 or mean > 220.0, round(mean, 2)


def check_edge_density(file_path: str) -> tuple[bool, float]:
    """True if < 2% of pixels are edges — flat/featureless image."""
    with Image.open(file_path) as img:
        arr = np.array(img.convert("L").filter(ImageFilter.FIND_EDGES))
    ratio = float((arr > 10).sum()) / arr.size
    return ratio < 0.02, round(ratio, 4)


def check_blur(file_path: str) -> tuple[bool, float]:
    """True if Laplacian variance < 100 — image is blurry."""
    with Image.open(file_path) as img:
        arr = np.array(img.convert("L"), dtype=np.float64)
    lap = (
        arr[:-2, 1:-1] + arr[2:, 1:-1] +
        arr[1:-1, :-2] + arr[1:-1, 2:] -
        4 * arr[1:-1, 1:-1]
    )
    variance = float(lap.var())
    return variance < 100.0, round(variance, 2)


def check_entropy(file_path: str) -> tuple[bool, float]:
    """True if image entropy < 3.0 bits — low information content."""
    with Image.open(file_path) as img:
        entropy = img.convert("L").entropy()
    return entropy < 3.0, round(entropy, 4)


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
    return score > 0.45, round(score, 4)
