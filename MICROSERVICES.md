# Microservices Architecture

This project implements the PRD microservice decomposition. The backend is `services/` (one process per service) plus `shared/` (the library they all import).

## Services

| Service | Port | Role |
|---------|------|------|
| **gateway** | 8000 | API Gateway / BFF — routes public `/api/v1/*` traffic |
| **auth** | 8001 | Google OAuth, sessions, `/auth/*` |
| **user-management** | 8002 | Departments, admins, users |
| **documents** | 8003 | PDF upload, metadata, elements |
| **ingestion-orchestrator** | 8004 | Job orchestration, `/ingestion/*` |
| **extraction** | 8010 | Docling PDF extraction (internal) |
| **chunking-indexing** | 8011 | Normalize, enrich, chunk, Qdrant upsert (internal) |
| **embedding** | 8012 | Embedding API (internal) |
| **sparse-retrieval** | 8013 | BM25 search (internal) |
| **retrieval** | 8014 | Hybrid dense+sparse+RRF, `/retrieval/*` |
| **generation** | 8015 | Groq/Qwen answer generation (internal) |
| **query** | 8016 | RAG query orchestration, `/query/*` |
| **dashboard** | 8017 | Dashboards, audit logs |
| **notifications** | 8018 | Redis job status events (optional) |

## Start

```bash
cd multimodal_rag_app
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs (via gateway — use individual service ports for service-specific docs)

## Request flow

### Upload + ingestion

```text
Client → gateway → documents (save PDF, create job)
                 → ingestion-orchestrator (/internal/v1/ingestion/run)
                      → extraction (Docling)
                      → chunking-indexing (chunk + upsert)
                      → notifications (Redis job events)
```

### Query

```text
Client → gateway → query
                      → retrieval (/internal/v1/retrieval/hybrid)
                      → generation (/internal/v1/generation/answer)
```

## Shared code

- `shared/rag_shared/` — models, schemas, routers, business logic, HTTP clients
- `rag/` — RAG pipeline library (Docling, Qdrant, Groq)

## Internal authentication

Service-to-service calls use header:

```http
X-Internal-Token: dev-internal-token
```

Set via `INTERNAL_SERVICE_TOKEN` in `.env`.

## Environment

Key variables (see `.env.example`):

- `USE_MICROSERVICES_PIPELINE=true` — query path uses retrieval + generation services
- `INTERNAL_SERVICE_TOKEN` — internal API auth
- `*_SERVICE_URL` — inter-service URLs (defaults work inside Docker Compose)

## Development

Run a single service locally:

```bash
export PYTHONPATH=/path/to/autonomous_agents:/path/to/autonomous_agents/multimodal_rag_app/shared
export $(grep -v '^#' .env | xargs)
cd services/auth
uvicorn main:app --reload --port 8001
```

## Project layout

```text
multimodal_rag_app/
  frontend/              # React UI
  shared/rag_shared/     # shared library
  services/
    gateway/
    auth/
    ...
  docker-compose.yml
```
