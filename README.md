# Extraction Service

FastAPI service that turns uploaded files into a canonical `document.json`. No CLI. No chunking or embeddings.

## Run with Docker

```bash
cp .env.example .env
# fill EURI_API_KEY (required only for chart/photo images and some video frames)
docker compose up --build
```

Health check: `GET http://localhost:8000/health`

```bash
curl -F "file=@sample.pdf" http://localhost:8000/api/v1/extractions
curl http://localhost:8000/api/v1/extractions/{job_id}
curl http://localhost:8000/api/v1/extractions/{job_id}/document
```

## Run locally (without OCR/Whisper)

```bash
python -m pip install -e ".[dev]"
uvicorn extraction.app:app --reload --app-dir src
```

Install OCR, Whisper, and Paddle with `python -m pip install -e ".[media]"`.

## Routing

| Input | Extractor |
| --- | --- |
| Dense PDF page | PyMuPDF |
| Sparse PDF page | PaddleOCR |
| DOCX / PPTX | python-docx / python-pptx |
| XLSX / XLS / CSV / TSV | openpyxl + pandas |
| Image with readable text | PaddleOCR |
| Chart / photo / diagram | Euron VLM |
| Audio | faster-whisper |
| Video | FFmpeg + faster-whisper; Euron VLM only if a frame needs vision |
| Zip | unpack with caps, then the same routing |
