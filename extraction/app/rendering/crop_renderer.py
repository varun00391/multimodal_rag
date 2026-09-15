from __future__ import annotations

from pathlib import Path

from PIL import Image


def crop_page_image(
    page_image_path: Path,
    bbox_px: list[float],
    dest: Path,
    padding: int = 4,
) -> Path:
    image = Image.open(page_image_path)
    x0, y0, x1, y1 = bbox_px
    left = max(0, int(x0) - padding)
    top = max(0, int(y0) - padding)
    right = min(image.width, int(x1) + padding)
    bottom = min(image.height, int(y1) + padding)
    if right <= left or bottom <= top:
        cropped = image.copy()
    else:
        cropped = image.crop((left, top, right, bottom))
    dest.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(dest)
    return dest
