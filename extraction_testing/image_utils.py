"""Crop a region from a rendered page image."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

CROP_PADDING = 4


def crop_region(
    page_image: str | Path,
    bbox: list[float],
    dest: str | Path | None = None,
    padding: int = CROP_PADDING,
) -> Path:
    source = Path(page_image)
    if not source.is_file():
        raise FileNotFoundError(f"Page image not found: {source}")
    image = Image.open(source)
    x0, y0, x1, y1 = bbox
    left = max(0, int(x0) - padding)
    top = max(0, int(y0) - padding)
    right = min(image.width, int(x1) + padding)
    bottom = min(image.height, int(y1) + padding)
    if right <= left or bottom <= top:
        cropped = image.copy()
    else:
        cropped = image.crop((left, top, right, bottom))
    if dest is None:
        dest_path = source.parent / f"_crop_{left}_{top}_{right}_{bottom}.png"
    else:
        dest_path = Path(dest)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
    cropped.save(dest_path)
    return dest_path
