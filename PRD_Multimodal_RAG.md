# Product Requirements Document (PRD)
## Multi-Modal RAG Application

**Version:** 1.1  
**Date:** 25 August 2026  
**Status:** Draft / Baseline for implementation

## 1. Product Vision

Build a secure multi-modal RAG application that lets authorized users ask questions about the full information content of PDFs, including text, tables, images, graphs, and scanned pages, without reducing the document to text-only retrieval.

Document ingestion is limited to Super Admin and Admin roles. Users consume indexed knowledge through query-only access within their authorized scope.

## 2. Product Goals

- High-quality multimodal document understanding.
- Reliable hybrid retrieval.
- Secure user/department isolation.
- Clear role separation: data contributors vs query-only users.
- Explainable retrieval and grounded generation.
- Operationally observable microservices.
- Simple administration for Super Admin and Admin.

## 3. Personas

### Super Admin

- Provisioned automatically on first Google login when email matches `SUPER_ADMIN_EMAIL` in `.env`.
- Needs centralized control, cross-department visibility, Admin/User management, document upload, and platform-level dashboards.
- Creates Admins by providing name, email, and department name.
- Can assign any User to any department or change a User's department.

### Admin

- Created by Super Admin with name, email, and department name.
- Needs to onboard/remove Users in the authorized department, upload documents, query department data, and monitor department usage.

### User

- Created by Admin (within department) or Super Admin (any department).
- Needs to ask questions and view query history/results for permitted documents.
- Must not upload documents or manage users.

## 4. Core Features

### 4.1 Authentication

- Google OAuth-based login.
- Capture authenticated email and identity information needed for authorization.
- Reject authenticated Google accounts that are not provisioned in the application (except the environment-defined Super Admin on first login).
- Maintain a secure application session/token strategy.

### 4.2 Authorization

Authorization is application-specific and separate from Google authentication.

**Environment configuration**

| Variable | Description |
|---|---|
| `SUPER_ADMIN_EMAIL` | Email address of the permanent Super Admin. Auto-provisioned on first Google login. Cannot be removed via admin APIs. |

**Recommended authorization entities**

- User
- Role (`SUPER_ADMIN`, `ADMIN`, `USER`)
- Department
- UserDepartmentAssignment
- DocumentOwnership / DocumentAccess

**Required rules**

1. Super Admin is defined by `SUPER_ADMIN_EMAIL` in `.env` and auto-provisioned on first login.
2. Super Admin cannot be removed or demoted through standard admin operations.
3. Super Admin creates Admin by providing **name**, **email**, and **department name** (department created if it does not exist).
4. Super Admin can add any User to any department and change a User's department assignment.
5. Admin creates User by providing **name** and **email** within the Admin's authorized department.
6. Only Super Admin and Admin can upload documents or add data to the system.
7. Super Admin, Admin, and User can ask questions against authorized document scope.
8. User cannot upload documents or perform any data-ingestion action.
9. Every document/query endpoint must enforce scope server-side.

**Permission summary**

| Action | Super Admin | Admin | User |
|---|---|---|---|
| Create Admin | Yes | No | No |
| Create User | Yes (any dept) | Yes (own dept) | No |
| Change User department | Yes | No | No |
| Upload PDF / add data | Yes | Yes | No |
| Query / ask questions | Yes | Yes | Yes |

### 4.3 Document Upload

**Authorization:** Super Admin and Admin only.

Input: PDF.

The upload flow should:

1. Validate caller role (reject User with `NOT_AUTHORIZED`).
2. Validate file type and size.
3. Create a document record scoped to uploader's department.
4. Persist the source file.
5. Start an asynchronous ingestion job.
6. Expose ingestion status.

Recommended statuses:
`UPLOADED -> QUEUED -> EXTRACTING -> CHUNKING -> EMBEDDING -> INDEXING -> READY`

Failure states:
`FAILED_EXTRACTION`, `FAILED_CHUNKING`, `FAILED_EMBEDDING`, `FAILED_INDEXING`.

### 4.4 PDF Extraction

The baseline extractor is Docling. It must preserve extracted information for:

- Text
- Tables
- Images
- Graphs
- Other supported document elements
- Page and positional metadata where available

For scanned PDFs, the extraction flow must support the relevant OCR/document-understanding behavior provided by the chosen extraction pipeline.

### 4.5 Parent-Child Chunking

The indexing pipeline shall create parent-child representations so that:

- Parent context retains broader document meaning.
- Child chunks support more precise retrieval.
- Each chunk retains document/page/element/type metadata.
- Chunks that originate from tables, images, or graphs can be traced back to their source element.

A recommended chunk metadata shape is:

```json
{
  "document_id": "doc_123",
  "chunk_id": "chunk_456",
  "parent_id": "parent_12",
  "page": 4,
  "element_type": "table",
  "source_ref": "page-4-element-7",
  "text": "...",
  "department_id": "dept_finance",
  "owner_user_id": "user_123"
}
```

### 4.6 Dense Indexing

- Generate embeddings using the selected Google embedding model.
- Store vectors in Qdrant.
- Store enough metadata for authorization filtering, traceability, and source reconstruction.

### 4.7 Sparse Indexing

- Build BM25 index over the searchable textual representation.
- Preserve document/chunk IDs so BM25 results can be joined with dense retrieval results.

### 4.8 Hybrid Retrieval

At query time:

1. Normalize and authorize the query context.
2. Generate a dense query embedding.
3. Perform dense retrieval from Qdrant.
4. Perform sparse BM25 retrieval.
5. Apply authorization filters to both retrieval paths.
6. Combine results using RRF.
7. Optionally rerank the top candidate set before context assembly.

The baseline retrieval design is BM25 + Google dense embeddings + RRF.

**Query authorization:** Super Admin, Admin, and User may all call query endpoints. Authorization filters determine which documents/chunks are visible based on role and department assignment.

### 4.9 Multimodal Context Assembly

The system should preserve and assemble retrieved evidence based on element type. For example:

- Text -> textual context.
- Table -> table representation plus relevant parent context.
- Image/graph -> original image or derived representation plus metadata/context.

The exact transport format to Qwen/Groq should be finalized during model integration based on the selected provider API.

### 4.10 Answer Generation

- Use a Qwen model exposed by Groq with native vision capability.
- Provide only authorized retrieved context.
- Prefer answers grounded in retrieved evidence.
- Return answer plus source references/metadata when available.
- Return an explicit no-evidence response when retrieval does not provide sufficient support.

Recommended response shape:

```json
{
  "query_id": "q_123",
  "answer": "...",
  "sources": [
    {
      "document_id": "doc_123",
      "page": 4,
      "chunk_id": "chunk_456",
      "element_type": "table"
    }
  ],
  "retrieval": {
    "dense_count": 5,
    "sparse_count": 5,
    "final_count": 6
  }
}
```

## 5. Views and Screens

### 5.1 Super Admin View

Recommended screens:

- Overview dashboard
- Department management
- Create Admin (name, email, department name)
- User management (all departments)
- Assign/change User department
- Document upload and data overview
- Ask question / chat
- Platform usage and operational metrics
- Search/query activity overview

### 5.2 Admin View

Recommended screens:

- Department dashboard
- User list
- Add/remove User (name, email)
- Upload document
- Ask question / chat
- User activity/data overview
- Department documents/usage overview

### 5.3 User View

Recommended screens:

- My dashboard
- Ask question / chat
- Query history
- Source/evidence viewer
- Permitted document list (read-only; no upload)

**Not available to User:** Upload document, user management, department management, Admin management.

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-001 | User can sign in with Google. | P0 |
| FR-002 | Unauthorized Google accounts cannot use protected application features. | P0 |
| FR-003 | Super Admin is auto-provisioned from `SUPER_ADMIN_EMAIL` on first login. | P0 |
| FR-004 | Super Admin can create Admin with name, email, and department name. | P0 |
| FR-005 | Super Admin cannot be removed through normal admin operations. | P0 |
| FR-006 | Super Admin can assign any User to any department. | P0 |
| FR-007 | Super Admin can change a User's department assignment. | P0 |
| FR-008 | Admin can add/remove Users in authorized department using name and email. | P0 |
| FR-009 | Super Admin and Admin can upload PDFs. | P0 |
| FR-010 | User cannot upload PDFs or add data. | P0 |
| FR-011 | Super Admin, Admin, and User can ask questions against authorized documents. | P0 |
| FR-012 | System exposes document processing status. | P0 |
| FR-013 | System extracts text, tables, images, graphs and other supported content. | P0 |
| FR-014 | System indexes parent-child chunks. | P0 |
| FR-015 | Dense vectors are stored in Qdrant. | P0 |
| FR-016 | BM25 index is available for sparse retrieval. | P0 |
| FR-017 | Retrieval combines dense and sparse results using RRF. | P0 |
| FR-018 | Query flow sends authorized multimodal evidence to Qwen/Groq. | P0 |
| FR-019 | User sees answer and source references. | P1 |
| FR-020 | Super Admin can see cross-department dashboards. | P1 |
| FR-021 | Admin cannot view other department data. | P0 |
| FR-022 | User cannot view another user's private query history. | P0 |
| FR-023 | System emits logs, traces, and metrics. | P0 |

## 7. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Security | Authorization must be enforced server-side on every protected data operation. Upload endpoints must reject User role regardless of client UI state. |
| Reliability | Ingestion failures must be represented as durable job/document states and be retryable where safe. |
| Observability | Each upload and query should carry a correlation/trace ID. |
| Performance | Measure and optimize P95 query latency and ingestion throughput. |
| Scalability | Services should scale independently where practical. |
| Maintainability | Microservices should have clear ownership and contracts. |
| Deployment | All services should be runnable using Docker Compose for development/integration environments. |
| Data isolation | Queries/retrieval must filter by authorized department/user scope. |
| Configuration | `SUPER_ADMIN_EMAIL` must be documented and validated at application startup where practical. |

## 8. Proposed Microservices

1. API Gateway / BFF
2. Auth Service
3. Authorization / User Management Service
4. Document Service
5. Ingestion Orchestrator
6. Extraction Service
7. Chunking / Indexing Service
8. Embedding Service
9. Sparse Retrieval Service
10. Retrieval / RRF Service
11. LLM / Generation Service
12. Query / Conversation Service
13. Dashboard / Analytics Service
14. Notification or Job Status Service (optional)
15. Observability stack components

For an MVP, some of these can be logically separated but deployed as fewer services to reduce operational complexity.

## 9. Data Model - Recommended Core Entities

- User (with `role`, `is_super_admin_seed`)
- Department
- UserDepartmentAssignment
- Document
- DocumentElement
- Chunk
- Query
- QueryResult / RetrievalEvent
- AuditLog
- IngestionJob
- Conversation (optional)

## 10. Product Analytics

Recommended metrics:

- Active users by role.
- Documents uploaded (by Super Admin vs Admin).
- Documents successfully indexed.
- Failed ingestions.
- Queries per day/user/department/role.
- Query latency.
- Retrieval hit rate.
- Dense vs sparse contribution.
- Blocked upload attempts by User role.
- Answer feedback if introduced.
- Storage/vector count.

## 11. Error Handling UX

The UI should distinguish:

- Invalid file.
- File too large.
- Upload failed.
- Upload not permitted (User role).
- Processing in progress.
- Processing failed.
- Document ready.
- No relevant evidence found.
- Model/provider unavailable.
- Unauthorized access.
- User not provisioned.
- Session expired.

## 12. Acceptance Criteria for MVP

A release is MVP-ready when:

1. `SUPER_ADMIN_EMAIL` is set in `.env` and Super Admin is auto-provisioned on first Google login.
2. Super Admin can create an Admin with name, email, and department name.
3. Super Admin can assign a User to a department and change department assignment.
4. Admin can authorize a User with name and email within the Admin's department.
5. Super Admin and Admin can upload a normal or scanned PDF.
6. User upload attempts are rejected with a clear authorization error.
7. The system can extract supported multimodal elements through Docling.
8. The system creates parent-child chunks.
9. Dense embeddings are indexed into Qdrant.
10. BM25 indexing is available.
11. Super Admin, Admin, and User queries execute dense + sparse retrieval and RRF within authorized scope.
12. The answer-generation service uses the Qwen model through Groq.
13. Users receive answers with traceable source references.
14. Cross-user and cross-department access tests pass.
15. Logs, traces, and metrics are visible for ingestion and query flows.
16. The complete local stack can be started with Docker Compose.
