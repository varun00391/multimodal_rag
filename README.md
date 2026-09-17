# Extraction + RAG service

FastAPI service that turns uploaded files into a canonical `document.json`, then indexes parent-child chunks into Qdrant Cloud and answers questions with Groq.

## Run with Docker

```bash
cp .env.example .env
# fill EURI_API_KEY, GROQ_API_KEY, QDRANT_URL, QDRANT_API_KEY
docker compose up --build
```

Health check: `GET http://localhost:8000/health`

```bash
curl -F "file=@sample.pdf" http://localhost:8000/api/v1/extractions
curl http://localhost:8000/api/v1/extractions/{job_id}
curl http://localhost:8000/api/v1/extractions/{job_id}/document
curl -X POST http://localhost:8000/api/v1/index -H 'Content-Type: application/json' -d '{"job_id":"{job_id}"}'
curl -X POST http://localhost:8000/api/v1/ask -H 'Content-Type: application/json' \
  -d '{"question":"What is the leave policy?","job_id":"{job_id}"}'
```

`POST /api/v1/ask` can omit `job_id` to search every indexed document.

## Run locally (without OCR/Whisper)

```bash
python -m pip install -e ".[dev]"
uvicorn extraction.app:app --reload --app-dir src
```

Install OCR, Whisper, and Paddle with `python -m pip install -e ".[media]"`.

## RAG

Indexing walks `document.json` (not the original file). Children are embedded with Euron `gemini-embedding-2-preview` (768-d text, including picture captions). Qdrant stores a dense vector plus a BM25 sparse vector. `/ask` fuses the two lists with RRF, drops dense-only hits below `RAG_SCORE_CUTOFF` (0.40), expands at most 3 parents, and answers with Groq.

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
