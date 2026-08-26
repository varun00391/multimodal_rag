# MultiModal RAG Frontend

React + Tailwind CSS frontend for the MultiModal RAG application, built from the UI/UX specification.

## Stack

- **React 19** + **TypeScript**
- **Vite** — dev server and build
- **Tailwind CSS v4** — styling
- **React Router** — routing and role guards
- **Lucide React** — icons

## Local development

```bash
cd multimodal_rag_app/frontend
npm install
cp .env.example .env
npm run dev
```

Open http://localhost:3000. The Vite dev server proxies `/api` to the backend gateway at http://localhost:8000.

Ensure the backend is running and `FRONTEND_URL=http://localhost:3000` is set in `multimodal_rag_app/.env`.

## Docker (via root compose)

From `multimodal_rag_app/`:

```bash
docker compose up --build frontend gateway postgres redis
```

Frontend: http://localhost:3000 (nginx serves the SPA and proxies `/api` to the gateway)

## Features

| Screen | Route | Roles |
|---|---|---|
| Login | `/login` | All |
| Dashboard | `/dashboard` | All (scoped) |
| Ask / RAG Chat | `/ask` | All |
| Documents | `/documents` | All (scoped) |
| Upload | `/documents/upload` | Super Admin, Admin |
| Document detail | `/documents/:id` | All (scoped) |
| History | `/history` | All |
| Departments | `/admin/departments` | Super Admin |
| Admins | `/admin/admins` | Super Admin |
| Users | `/admin/users` | Super Admin, Admin |
| Analytics | `/analytics` | Super Admin, Admin |
| Profile | `/profile` | All |

## Project structure

```
src/
  api/           # Typed API client layer
  app/           # Routing, layouts, guards
  components/    # Shared UI components
  features/      # Feature pages
  hooks/         # Auth, toast
  types/         # API/domain types
  utils/         # Permissions, formatting
```
