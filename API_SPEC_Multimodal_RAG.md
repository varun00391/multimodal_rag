# API Specification - Multi-Modal RAG Application

**Version:** 1.1  
**Date:** 25 August 2026

This API design translates the product requirements into recommended service contracts. Endpoint names and payloads are implementation recommendations aligned with the role model defined in the BRD and PRD.

## 1. API Architecture

Recommended edge pattern:

`Client -> API Gateway/BFF -> Internal Microservices`

External clients should preferably call the Gateway/BFF rather than directly invoking internal services.

All protected requests should carry an authenticated identity/session token. Authorization must be re-evaluated at the server for every protected resource operation.

## 2. Environment Configuration

| Variable | Required | Description |
|---|---|---|
| `SUPER_ADMIN_EMAIL` | Yes | Email of the permanent Super Admin. On first Google login with this email, the system auto-provisions a `SUPER_ADMIN` account. This account cannot be removed or demoted via admin APIs. |

Example `.env`:

```env
SUPER_ADMIN_EMAIL=superadmin@company.com
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
SESSION_SECRET_KEY=...
```

## 3. Role Model and Authorization Matrix

| Role | Create Admin | Create User | Change User Dept | Upload Data | Query |
|---|---|---|---|---|---|
| `SUPER_ADMIN` | Yes | Yes (any dept) | Yes | Yes | Yes |
| `ADMIN` | No | Yes (own dept) | No | Yes | Yes |
| `USER` | No | No | No | **No** | Yes |

Authorization enforcement:

- Upload, document delete, and ingestion-start endpoints require `SUPER_ADMIN` or `ADMIN`.
- Query and retrieval endpoints allow `SUPER_ADMIN`, `ADMIN`, and `USER` with scope filtering.
- Admin-management endpoints require `SUPER_ADMIN`.
- User-management endpoints require `SUPER_ADMIN` or `ADMIN` (Admin scoped to own department).

## 4. API Domains

| Domain | Service |
|---|---|
| Authentication | Auth Service |
| Users/Admins/Departments | Authorization & User Service |
| Documents | Document Service |
| Ingestion | Ingestion Orchestrator |
| Extraction | Extraction Service |
| Indexing | Chunking/Indexing Service |
| Embeddings | Embedding Service |
| Retrieval | Retrieval Service |
| Generation | LLM Service |
| Queries/Chat | Query Service |
| Dashboards | Analytics Service |
| Health/Observability | Platform/Operational endpoints |

## 5. Authentication APIs

### GET /api/v1/auth/google/login

Starts or returns the Google OAuth login flow.

### GET /api/v1/auth/google/callback

Receives the provider callback and establishes application authentication.

**Super Admin bootstrap behavior:**

- If authenticated email matches `SUPER_ADMIN_EMAIL`, auto-provision or upgrade user to `SUPER_ADMIN` with `is_super_admin_seed=true`.
- Otherwise, user must already exist in the application (created by Super Admin or Admin).

### GET /api/v1/auth/me

Returns authenticated identity and application authorization.

Response example (Super Admin):

```json
{
  "user_id": "u_123",
  "email": "superadmin@company.com",
  "name": "Super Admin",
  "role": "SUPER_ADMIN",
  "department_ids": [],
  "status": "ACTIVE",
  "is_super_admin_seed": true
}
```

Response example (Admin):

```json
{
  "user_id": "u_456",
  "email": "admin@company.com",
  "name": "Finance Admin",
  "role": "ADMIN",
  "department_ids": ["dept_finance"],
  "status": "ACTIVE",
  "is_super_admin_seed": false
}
```

Response example (User):

```json
{
  "user_id": "u_789",
  "email": "user@company.com",
  "name": "Normal User",
  "role": "USER",
  "department_ids": ["dept_finance"],
  "status": "ACTIVE",
  "is_super_admin_seed": false
}
```

### POST /api/v1/auth/logout

Ends the current application session.

## 6. Department APIs

### GET /api/v1/departments

**Authorization:** Super Admin.

Returns all departments.

### POST /api/v1/departments

**Authorization:** Super Admin.

Create department explicitly (optional; departments are also created implicitly when Super Admin creates an Admin with a new department name).

Request:

```json
{
  "name": "Finance"
}
```

### GET /api/v1/departments/{department_id}

**Authorization:** Super Admin, or Admin assigned to the department.

Returns department information subject to role scope.

## 7. Admin Management APIs

### POST /api/v1/admins

**Authorization:** Super Admin only.

Creates an Admin with name, email, and department name. If the department does not exist, it is created and the Admin is assigned to it.

Request:

```json
{
  "name": "Finance Admin",
  "email": "admin@company.com",
  "department_name": "Finance"
}
```

Response:

```json
{
  "user_id": "u_456",
  "email": "admin@company.com",
  "name": "Finance Admin",
  "role": "ADMIN",
  "department_ids": ["dept_finance"],
  "status": "ACTIVE"
}
```

Errors:

- `NOT_AUTHORIZED` — caller is not Super Admin.
- `USER_ALREADY_EXISTS` — email already registered with incompatible role.

### GET /api/v1/departments/{department_id}/admins

**Authorization:** Super Admin.

List Admins assigned to a department.

### DELETE /api/v1/departments/{department_id}/admins/{user_id}

**Authorization:** Super Admin.

Remove an Admin from a department or deactivate the Admin account per policy.

**Constraint:** Users with `is_super_admin_seed=true` must not be removable via this route.

## 8. User Management APIs

### GET /api/v1/departments/{department_id}/users

**Authorization:** Admin (own department) or Super Admin (any department).

List Users in the department.

### POST /api/v1/departments/{department_id}/users

**Authorization:**

- **Admin** — may add Users to departments they manage.
- **Super Admin** — may add Users to any department.

Creates or activates a normal User and assigns them to the department.

Request:

```json
{
  "name": "User Name",
  "email": "user@company.com"
}
```

Response:

```json
{
  "user_id": "u_789",
  "email": "user@company.com",
  "name": "User Name",
  "role": "USER",
  "department_ids": ["dept_finance"],
  "status": "ACTIVE"
}
```

### DELETE /api/v1/departments/{department_id}/users/{user_id}

**Authorization:** Admin (own department) or Super Admin.

Remove/deauthorize a User from the department.

### PATCH /api/v1/users/{user_id}/department

**Authorization:** Super Admin only.

Assign a User to a different department or add an additional department assignment according to the chosen data model.

Request:

```json
{
  "department_id": "dept_hr"
}
```

Response:

```json
{
  "user_id": "u_789",
  "email": "user@company.com",
  "name": "User Name",
  "role": "USER",
  "department_ids": ["dept_hr"],
  "status": "ACTIVE"
}
```

**Notes:**

- Super Admin is the only role that may change a User's department assignment.
- Admin cannot move Users across departments.

### PATCH /api/v1/users/{user_id}/status

**Authorization:** Super Admin, or Admin for Users in own department.

Activate/deactivate a user.

Request:

```json
{
  "status": "INACTIVE"
}
```

## 9. Document APIs

### POST /api/v1/documents

**Authorization:** Super Admin or Admin only. **User role must receive `403 NOT_AUTHORIZED`.**

Upload a PDF.

Multipart form-data:

- `file` (required)
- `title` (optional)
- optional metadata fields

Response:

```json
{
  "document_id": "doc_123",
  "status": "QUEUED",
  "ingestion_job_id": "job_123"
}
```

Errors:

- `NOT_AUTHORIZED` — User attempted upload.
- `INVALID_FILE_TYPE`
- `FILE_TOO_LARGE`

### GET /api/v1/documents

**Authorization:** Super Admin, Admin, User (scoped).

List documents visible to the caller.

Recommended filters:

- `status`
- `department_id` (only when authorized)
- `owner_user_id` (only when authorized)
- `page`
- `page_size`

Scope rules:

- **Super Admin** — all documents.
- **Admin** — documents in assigned department(s).
- **User** — documents in assigned department(s); read-only listing.

### GET /api/v1/documents/{document_id}

**Authorization:** Scoped by role and department.

Get document metadata and ingestion status.

### DELETE /api/v1/documents/{document_id}

**Authorization:** Super Admin or Admin (within authorized department scope).

Delete a document and its associated index artifacts.

### GET /api/v1/documents/{document_id}/elements

**Authorization:** Scoped by role and department.

Inspect extracted elements for a document.

### GET /api/v1/documents/{document_id}/elements/{element_id}

**Authorization:** Scoped by role and department.

Get one extracted element and source metadata.

## 10. Ingestion APIs

### POST /api/v1/ingestion/{document_id}/start

**Authorization:** Super Admin or Admin only.

Starts or retries ingestion for an authorized document.

### GET /api/v1/ingestion/jobs/{job_id}

**Authorization:** Super Admin, Admin, or User (if document is visible).

Returns:

```json
{
  "job_id": "job_123",
  "document_id": "doc_123",
  "status": "EMBEDDING",
  "progress": 72,
  "current_step": "Generating dense embeddings"
}
```

### POST /api/v1/ingestion/jobs/{job_id}/retry

**Authorization:** Super Admin or Admin only.

Retries a failed job where safe.

## 11. Internal Extraction APIs

These endpoints are recommended as internal service contracts and should not normally be exposed publicly.

### POST /internal/v1/extraction/extract

Input: document reference. Output: normalized Docling-derived document structure.

### GET /internal/v1/extraction/documents/{document_id}

Returns extraction status/results.

## 12. Internal Chunking/Indexing APIs

### POST /internal/v1/indexing/chunk

Creates parent-child chunks from extracted elements.

### POST /internal/v1/indexing/embed

Creates dense embeddings for indexable chunks.

### POST /internal/v1/indexing/upsert

Writes vectors and metadata to Qdrant and updates the sparse/BM25 index.

### DELETE /internal/v1/indexing/documents/{document_id}

Removes all index artifacts for a document.

## 13. Retrieval APIs

### POST /api/v1/retrieval/search

**Authorization:** Super Admin, Admin, User (scoped).

Recommended request:

```json
{
  "query": "What was the revenue growth shown in the graph?",
  "top_k_dense": 10,
  "top_k_sparse": 10,
  "final_top_k": 8,
  "document_ids": ["doc_123"]
}
```

The server must apply authorization constraints before returning results.

Response:

```json
{
  "results": [
    {
      "chunk_id": "chunk_01",
      "document_id": "doc_123",
      "page": 8,
      "element_type": "graph",
      "score": 0.82,
      "retrieval_sources": ["dense", "sparse"]
    }
  ]
}
```

### POST /internal/v1/retrieval/hybrid

Internal orchestration endpoint for:

- Dense retrieval from Qdrant.
- BM25 retrieval.
- RRF fusion.
- Optional reranking.

## 14. Query / RAG APIs

### POST /api/v1/query

**Authorization:** Super Admin, Admin, User (scoped).

This is the main end-user RAG endpoint. All provisioned roles may ask questions; authorization filters determine accessible document scope.

Request:

```json
{
  "query": "Summarize the reasons for the decline shown in the report.",
  "document_ids": ["doc_123"],
  "conversation_id": null
}
```

Response:

```json
{
  "query_id": "q_001",
  "answer": "...",
  "sources": [
    {
      "document_id": "doc_123",
      "page": 6,
      "chunk_id": "chunk_77",
      "element_type": "text"
    },
    {
      "document_id": "doc_123",
      "page": 7,
      "chunk_id": "chunk_81",
      "element_type": "graph"
    }
  ],
  "usage": {
    "retrieved_chunks": 8
  }
}
```

### POST /api/v1/query/stream

**Authorization:** Super Admin, Admin, User (scoped).

Streaming version for chat UX.

### GET /api/v1/query/{query_id}

**Authorization:** Query owner, or Admin/Super Admin per policy.

Returns query status, result, and source references where persisted.

### GET /api/v1/users/me/queries

**Authorization:** Authenticated user.

Returns the current user's query history.

## 15. Internal LLM APIs

### POST /internal/v1/generation/answer

Responsibilities:

- Assemble authorized multimodal context.
- Build prompt/messages.
- Send request to the Qwen model through Groq.
- Normalize provider response.
- Return answer + metadata.

Recommended request:

```json
{
  "query": "...",
  "contexts": [
    {
      "type": "text",
      "content": "...",
      "page": 4
    },
    {
      "type": "image",
      "image_ref": "...",
      "page": 4
    }
  ]
}
```

## 16. Dashboard APIs

### GET /api/v1/dashboard/me

**Authorization:** User.

Normal User dashboard (query activity, no upload metrics).

### GET /api/v1/dashboard/departments/{department_id}

**Authorization:** Admin (own department) or Super Admin.

Department dashboard including users, documents, ingestion, and queries.

### GET /api/v1/dashboard/super-admin

**Authorization:** Super Admin.

Cross-department dashboard.

Recommended metrics:

- users by role
- documents uploaded by Super Admin vs Admin
- ingestion success/failure
- queries by role/department
- query latency
- blocked upload attempts

## 17. Audit / Observability APIs

### GET /api/v1/audit-logs

Administrative audit access according to role.

Recommended audited events:

- Super Admin login/bootstrap
- Admin created
- User created/removed
- User department changed
- Document uploaded/deleted
- Blocked upload attempt by User

### GET /health

Service health.

### GET /ready

Readiness check.

### GET /metrics

Prometheus-style metrics endpoint for services, if selected.

Tracing should be propagated through headers/correlation IDs rather than relying only on an application endpoint.

## 18. Error Contract

Use a consistent structure across services:

```json
{
  "error": {
    "code": "DOCUMENT_ACCESS_DENIED",
    "message": "You do not have access to this document.",
    "request_id": "req_123"
  }
}
```

Recommended codes:

- `AUTH_REQUIRED`
- `AUTH_INVALID`
- `NOT_AUTHORIZED`
- `USER_NOT_PROVISIONED`
- `USER_ALREADY_EXISTS`
- `DEPARTMENT_NOT_FOUND`
- `DOCUMENT_NOT_FOUND`
- `DOCUMENT_ACCESS_DENIED`
- `UPLOAD_NOT_PERMITTED`
- `INVALID_FILE_TYPE`
- `FILE_TOO_LARGE`
- `INGESTION_IN_PROGRESS`
- `INGESTION_FAILED`
- `RETRIEVAL_FAILED`
- `LLM_PROVIDER_ERROR`
- `RATE_LIMITED`
- `INTERNAL_ERROR`

Example — User upload blocked:

```json
{
  "error": {
    "code": "NOT_AUTHORIZED",
    "message": "Only Super Admin and Admin can upload or manage documents.",
    "request_id": "req_456"
  }
}
```

## 19. API Security Rules

1. Validate Google identity at the authentication boundary.
2. Bootstrap Super Admin only when authenticated email matches `SUPER_ADMIN_EMAIL`.
3. Never trust a `department_id` or `user_id` supplied by the client without server-side authorization checks.
4. Enforce upload restrictions server-side; do not rely on UI hiding alone.
5. Apply authorization filters to document listing, retrieval, deletion, and query context.
6. Only Super Admin may change User department assignments.
7. Protect users with `is_super_admin_seed=true` from removal/demotion via admin APIs.
8. Propagate the authenticated subject and authorization scope to internal services.
9. Protect internal APIs from direct public access.
10. Audit privileged admin operations and blocked upload attempts.
11. Do not expose raw vector-store or storage credentials to clients.

## 20. Suggested API Versioning

Use URI versioning (`/api/v1/...`) initially. Keep provider-specific APIs behind internal service boundaries so changing embedding or LLM providers does not require redesigning the public client API.

## 21. Changelog

| Version | Date | Changes |
|---|---|---|
| 1.0 | 25 Aug 2026 | Initial API specification |
| 1.1 | 25 Aug 2026 | Added `SUPER_ADMIN_EMAIL` bootstrap; Super Admin creates Admin with department name; Super Admin department reassignment; upload restricted to Super Admin/Admin; query allowed for all roles; updated authorization matrix and error codes |
