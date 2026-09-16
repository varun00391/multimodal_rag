"""Profile, render, route, extract text (OCR) and visuals (Euron VLM).

    python main.py
    python main.py /path/to/file.pdf
"""

import sys

from pdf_profiler import main

# Optional: put file or folder paths here instead of using the command line.
# Missing paths are ignored so Docker can rely on ./inputs instead.
PDF_PATHS: list[str] = [
    "/Users/varunnegi/autonomous_agents/multimodal_rag_app/extraction_testing/2309.06180v1-2.pdf",
]


if __name__ == "__main__":
    from pathlib import Path

    cli = sys.argv[1:]
    existing = [path for path in PDF_PATHS if Path(path).is_file()]
    if cli and not cli[0].startswith("-"):
        argv = cli
    elif existing:
        argv = existing + cli
    else:
        argv = cli or None
    raise SystemExit(main(argv))
