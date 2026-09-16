from __future__ import annotations

import zipfile
from pathlib import Path

from extraction.errors import ExtractionError
from extraction.settings import Settings


def unpack_zip(settings: Settings, path: Path, dest: Path) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ExtractionError("ZIP_INVALID", "File is not a valid zip archive.") from exc
    names = archive.namelist()
    if len(names) > settings.zip_max_files:
        raise ExtractionError("ZIP_TOO_MANY_FILES", f"Zip has more than {settings.zip_max_files} entries.")
    total = 0
    extracted: list[Path] = []
    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = info.filename.replace("\\", "/")
            if name.startswith("/") or ".." in Path(name).parts:
                raise ExtractionError("ZIP_UNSAFE_PATH", f"Unsafe zip member: {info.filename}")
            total += info.file_size
            if total > settings.zip_max_bytes:
                raise ExtractionError("ZIP_TOO_LARGE", f"Uncompressed zip exceeds {settings.zip_max_bytes} bytes.")
            target = dest / Path(name).name
            with archive.open(info) as source, target.open("wb") as out:
                out.write(source.read())
            extracted.append(target)
    return extracted
