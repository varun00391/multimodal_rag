# Multimodal RAG Backend

FastAPI backend for the Multi-Modal RAG application, wired to the Docling + Qdrant + Groq pipeline in the parent `rag/` package.

**Architecture:** PRD microservices — see [MICROSERVICES.md](./MICROSERVICES.md).

## Stack

- **FastAPI** — REST API (14 microservices + gateway)
- **PostgreSQL** — users, departments, documents, jobs, queries
- **Redis** — job notifications
- **Docling** — PDF extraction (text, tables, images)
- **Groq** — vision enrichment + answer generation
- **EURI/Gemini** — embeddings
- **Qdrant Cloud** — vector index
- **BM25 + RRF** — hybrid retrieval

## Quick start

```bash
cd multimodal_rag_app
cp .env.example .env
# Set SUPER_ADMIN_EMAIL, SESSION_SECRET_KEY, Google OAuth,
# GROQ_API_KEY, EURI_API_KEY, QDRANT_URL, QDRANT_API_KEY

docker compose up --build
```

**Frontend:** http://localhost:3000  
**API:** http://localhost:8000  
**Swagger:** http://localhost:8000/docs  
**Health:** http://localhost:8000/health

The React frontend (port 3000) proxies API calls to the gateway. After Google OAuth, you are redirected back to the frontend.

## Complete end-to-end flow

### 1. Authenticate

1. Open http://localhost:3000 and click **Continue with Google**
2. Sign in with the Google account matching `SUPER_ADMIN_EMAIL`
3. After redirect, you return to the frontend dashboard (session cookie is shared via the gateway)

Verify: `GET /api/v1/auth/me` or open **Profile** in the UI

### 2. Create department + admin (first-time setup)

**Super Admin only**

1. `POST /api/v1/admins`

```json
{
  "name": "Tech Admin",
  "email": "admin@example.com",
  "department_name": "tech"
}
```

2. `GET /api/v1/departments` — copy the `department_id` UUID (not the name)

### 3. Upload a PDF

**Super Admin or Admin**

`POST /api/v1/documents` (multipart form)

| Field | Value |
|---|---|
| `file` | your PDF |
| `title` | optional |
| `department_id` | UUID from step 2 |

Response includes `document_id` and `ingestion_job_id`.

**Ingestion starts automatically** after upload.

### 4. Poll ingestion status

`GET /api/v1/ingestion/jobs/{job_id}`

Status progression:

`QUEUED` → `EXTRACTING` → `CHUNKING` → `EMBEDDING` → `INDEXING` → `COMPLETED`

When `status` is `COMPLETED` and `progress` is `100`, the document is ready.

Manual re-run (if needed):

- `POST /api/v1/ingestion/{document_id}/start`
- `POST /api/v1/ingestion/jobs/{job_id}/retry` (failed jobs only)

### 5. Inspect extracted content

`GET /api/v1/documents/{document_id}/elements`

Returns text/table/image elements extracted from the PDF.

### 6. Hybrid retrieval (optional)

`POST /api/v1/retrieval/search`

```json
{
  "query": "What is the main contribution?",
  "document_ids": ["890439d0-8c00-4748-8789-e9fe8d3e8b80"],
  "top_k_dense": 10,
  "top_k_sparse": 10,
  "final_top_k": 7
}
```

### 7. Ask a RAG question

`POST /api/v1/query`

```json
{
  "query": "Explain the architecture in this document",
  "document_ids": ["890439d0-8c00-4748-8789-e9fe8d3e8b80"]
}
```

Returns an answer with source citations.

Streaming variant: `POST /api/v1/query/stream`

### 8. Query history

`GET /api/v1/users/me/queries`

---

## Pipeline architecture

```text
Upload PDF
  → save file + create Document/IngestionJob
  → background worker:
      Docling extract → normalize → Groq vision enrich → chunk → embed → Qdrant upsert
  → persist DocumentElement rows
  → Document.status = READY

Query
  → load children/parents from /data/uploads/workspaces/{document_id}/
  → dense (Qdrant) + sparse (BM25) + RRF
  → Groq Qwen answer generation
```

Workspace layout inside the API container:

```text
/data/uploads/
  {uuid}_{filename}.pdf          # original upload
  workspaces/{document_id}/
    {document_id}.pdf
    document.json
    images/
    rag/parents.jsonl
    rag/children.jsonl
```

## Required environment variables

| Variable | Purpose |
|---|---|
| `SUPER_ADMIN_EMAIL` | Bootstrap Super Admin on first Google login |
| `SESSION_SECRET_KEY` | Session cookie signing |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth |
| `GROQ_API_KEY` | Vision enrichment + answer generation |
| `EURI_API_KEY` | Embeddings |
| `QDRANT_URL` / `QDRANT_API_KEY` | Vector database |
| `DATABASE_URL` / `REDIS_URL` | Set by docker-compose |

## Authorization

Roles: `SUPER_ADMIN`, `ADMIN`, `USER`

- Upload/delete: Super Admin + Admin
- Query/retrieval: all roles (scoped by department)
- Documents are isolated by `department_id`

## Troubleshooting

| Symptom | Fix |
|---|---|
| Ingestion stuck at `QUEUED` | Check `docker compose logs ingestion-orchestrator extraction` for errors |
| `DEPARTMENT_NOT_FOUND` on upload | Use department UUID from `GET /departments`, not the name |
| Query returns 404 | Wait until ingestion job is `COMPLETED` |
| OAuth redirect to dead page | Open `/docs` on port 8000 after login |
| Docling/OOM in Docker | Increase Docker memory; large PDFs need 4GB+ |

## Local development (without Docker)

Run a single service (example: auth). Requires local PostgreSQL, Redis, and the same API keys in `.env`.

```bash
cd multimodal_rag_app
python -m venv .venv && source .venv/bin/activate
pip install -r shared/requirements.txt
export PYTHONPATH=/path/to/autonomous_agents:/path/to/autonomous_agents/multimodal_rag_app/shared
export $(grep -v '^#' .env | xargs)
cd services/auth
uvicorn main:app --reload --port 8001
```

See [MICROSERVICES.md](./MICROSERVICES.md) for ports and the full service list. Prefer `docker compose up --build` to run the whole stack.
