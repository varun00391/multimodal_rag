"""FastAPI wrapper around the extraction_testing pipeline.

Upload a PDF and receive extracted text, visuals, regions, and a summary.

    uvicorn api:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import re
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from pdf_profiler import OUTPUTS_DIR, process_pdf
from page_renderer import DEFAULT_DPI

MAX_PDF_BYTES = 50 * 1024 * 1024
_PIPELINE_LOCK = threading.Lock()

UPLOAD_FORM = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>PDF extraction</title>
  <style>
    body { font-family: sans-serif; max-width: 960px; margin: 2rem auto; padding: 0 1rem; }
    form { display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap; }
    button { padding: 0.4rem 0.9rem; }
    pre { background: #111; color: #eee; padding: 1rem; overflow: auto; min-height: 8rem; }
    .hint { color: #555; }
  </style>
</head>
<body>
  <h1>PDF extraction</h1>
  <p class="hint">Upload a PDF. The pipeline profiles, renders, routes, then extracts text (OCR) and visuals (VLM).</p>
  <form id="extract-form">
    <input type="file" name="file" accept="application/pdf" required>
    <button type="submit">Extract</button>
  </form>
  <p id="status" class="hint"></p>
  <pre id="output"></pre>
  <script>
    const form = document.getElementById("extract-form");
    const status = document.getElementById("status");
    const output = document.getElementById("output");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const body = new FormData(form);
      status.textContent = "Extracting… this can take several minutes.";
      output.textContent = "";
      try {
        const response = await fetch("/extract", { method: "POST", body });
        const data = await response.json();
        if (!response.ok) {
          status.textContent = "Extraction failed.";
          output.textContent = JSON.stringify(data, null, 2);
          return;
        }
        status.textContent = "Done. Showing summary, text, and visuals (full JSON below).";
        output.textContent = JSON.stringify(data, null, 2);
      } catch (error) {
        status.textContent = "Request failed.";
        output.textContent = String(error);
      }
    });
  </script>
</body>
</html>
"""


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from ocr_engine import get_ocr_engine
    from settings import load_settings

    load_settings()
    get_ocr_engine()
    yield


app = FastAPI(
    title="PDF extraction API",
    version="0.1.0",
    description="Upload a PDF and run the multimodal extraction pipeline.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _safe_stem(filename: str | None) -> str:
    stem = Path(filename or "upload.pdf").stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._") or "upload"
    return cleaned[:80]


@app.get("/", response_class=HTMLResponse)
def index():
    return UPLOAD_FORM


@app.get("/health")
def health():
    from ocr_engine import active_ocr_engine
    from settings import load_settings

    settings = load_settings()
    return {
        "status": "ok",
        "ocr_engine": active_ocr_engine(),
        "vlm_provider": "euron",
        "vlm_model": settings["euri_vlm_model"],
    }


@app.post("/extract")
async def extract_pdf(
    file: UploadFile = File(..., description="PDF file to extract"),
    dpi: int = Query(DEFAULT_DPI, ge=72, le=400),
    include_native: bool = Query(False, description="Include bulky native PDF objects"),
):
    filename = file.filename or "upload.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload a .pdf file.")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="PDF is larger than 50 MB.")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="File is not a PDF.")

    stem = _safe_stem(filename)
    run_id = uuid.uuid4().hex[:8]
    doc_dir = OUTPUTS_DIR / f"{stem}_{run_id}"
    pdf_path = doc_dir / f"{stem}.pdf"
    doc_dir.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(data)

    def _run() -> dict:
        with _PIPELINE_LOCK:
            return process_pdf(
                pdf_path,
                output_dir=doc_dir,
                dpi=dpi,
                include_native=include_native,
            )

    try:
        result = await asyncio.to_thread(_run)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    result["ok"] = True
    return result
