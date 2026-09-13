# Nexus — Multimodal RAG Prototype

Rapid prototype of a multimodal retrieval workspace: upload PDFs, images, video, and other files (or sync connectors), ask grounded questions, and inspect usage, tokens, latency, cost, and model mix.

## Stack

- **Backend:** Python, FastAPI, SQLite, TF-IDF retrieval, optional OpenAI generation
- **Frontend:** React, Vite, Tailwind CSS, Recharts
- **Run:** Docker Compose (separate Dockerfiles for API and UI)

## Quick start (Docker)

```bash
cd multimodal_rag_app/rapid_prototype
cp .env.example .env   # optional: set OPENAI_API_KEY
docker compose up --build
```

Open [http://localhost:3000](http://localhost:3000).

Demo login:

- Email: `demo@nexus.ai`
- Password: `demo1234`

The demo account is preloaded with sample files, connectors, conversations, and 28 days of usage telemetry.

## Local development

Terminal 1:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
npm install
npm run dev
```

UI: [http://localhost:5173](http://localhost:5173) (proxies `/api` to the backend).

## What is included

- Login / register with JWT sessions
- File library with drag-and-drop ingest (PDF, Office, images, video, audio, text)
- Chat with source citations, model picker, and source filters
- Connectors: Google Drive, Gmail, Outlook, OneDrive, Dropbox, Slack, Notion, SharePoint (simulated OAuth + sample sync)
- Usage dashboard: questions, tokens, avg latency, total cost, model distribution, recent questions
- Settings for default model and optional OpenAI key
- Health check at `/api/health`

Without `OPENAI_API_KEY`, answers are extractive (retrieved chunks, composed locally) and still tracked for tokens, latency, and cost.

## API surface

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/login` | Sign in |
| GET | `/api/auth/me` | Current user |
| POST | `/api/documents/upload` | Multipart file ingest |
| GET | `/api/documents` | Library |
| POST | `/api/chat` | Ask a question |
| GET | `/api/connectors` | Connector catalog + status |
| POST | `/api/connectors/{provider}/connect` | Connect |
| POST | `/api/connectors/{provider}/sync` | Pull sample items |
| GET | `/api/dashboard` | Usage KPIs and series |

## Notes

This is an MVP prototype: connectors do not call live OAuth providers, embeddings are TF-IDF (no GPU), and SQLite is the store. Plug in real OAuth, a vector database, and a vision/ASR pipeline for production.
