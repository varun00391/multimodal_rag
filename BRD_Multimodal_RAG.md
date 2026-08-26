# Business Requirements Document (BRD)
## Multi-Modal RAG Application

**Version:** 1.1  
**Date:** 25 August 2026  
**Status:** Draft / Baseline for implementation

## 1. Executive Summary

The product is a multi-modal Retrieval-Augmented Generation (RAG) application that allows authorized users to ask natural-language questions against indexed PDF documents containing text, tables, images, graphs, scanned pages, and other document information.

The proposed solution uses Docling for document understanding and extraction, parent-child chunking for indexing, Google embeddings with Qdrant for vector storage, hybrid retrieval using BM25 + dense retrieval with Reciprocal Rank Fusion (RRF), and a Qwen vision-capable model through Groq for answer generation.

The application uses Google authentication plus application-level role-based authorization. It has three roles: **Super Admin**, **Admin**, and **User**. A Super Admin is provisioned by email address configured in the application environment (`.env`). Only Super Admin and Admin can upload documents and manage indexed data; Users can query permitted documents but cannot add data to the system.

The application will be built as microservices, include logging, tracing, and metrics, and be containerized with Docker Compose.

## 2. Business Problem

Conventional text-only RAG systems can lose information contained in tables, images, graphs, layouts, or scanned pages. The business requirement is to preserve the information extracted from heterogeneous PDFs so users can ask questions about any meaningful content in the document rather than only plain text.

The application also needs departmental access isolation, centralized administration, and strict role separation between data contributors (Super Admin and Admin) and query-only users (User).

## 3. Business Objectives

1. Enable question answering over heterogeneous PDF content.
2. Preserve text, tables, images, graphs, and scanned-document information during ingestion.
3. Improve retrieval quality by combining sparse and dense retrieval.
4. Provide grounded answers through a vision-capable LLM.
5. Enforce department- and user-level data isolation.
6. Give Super Admins centralized visibility and administration.
7. Restrict document ingestion to Super Admin and Admin roles only.
8. Allow all provisioned roles to ask questions against authorized document scope.
9. Provide operational observability through logs, traces, and metrics.
10. Deploy the application as Dockerized microservices.

## 4. Stakeholders

| Stakeholder | Responsibility / Interest |
|---|---|
| Super Admin | Platform owner provisioned via `.env`; creates Admins, manages cross-department user assignments, uploads documents, queries data, views cross-department dashboards |
| Admin | Manages Users within assigned department(s), uploads documents, queries department data |
| User | Queries permitted documents only; cannot upload or manage data |
| Platform / Engineering Team | Build, deploy, operate, monitor, and secure the system |
| Department / Business Owner | Define departmental usage and access expectations |

## 5. User Roles and Access Model

### 5.1 Super Admin

**Provisioning**

- The Super Admin is defined by email address in the application environment variable `SUPER_ADMIN_EMAIL` (`.env` file).
- On first Google login with the configured email, the system auto-provisions a permanent Super Admin account.
- The Super Admin cannot be removed or demoted through normal admin management flows.

**Capabilities**

- Authenticate using Google.
- Create an Admin by providing **name**, **email**, and **department name**.
  - If the department does not exist, the system creates it.
  - The new Admin is assigned to that department.
- Add any User to any department.
- Change a User's department assignment.
- Upload PDF documents and manage indexed data within authorized scope.
- Ask questions against uploaded/indexed documents.
- View data and dashboards for all departments, Admins, and Users.

### 5.2 Admin

**Provisioning**

- Created exclusively by the Super Admin via name, email, and department name.
- Must authenticate using Google after being provisioned.

**Capabilities**

- Add Users within the Admin's authorized department(s) by providing **name** and **email**.
- Remove/deactivate Users within the authorized department scope.
- Upload PDF documents for the authorized department.
- Ask questions against documents in the authorized department scope.
- View department dashboards, users, documents, and query activity for the authorized department.
- Must not see or manage data belonging to other departments unless explicitly assigned.

### 5.3 User

**Provisioning**

- Created by an Admin (within the Admin's department) or by the Super Admin (any department).
- Must authenticate using Google after being provisioned.

**Capabilities**

- Ask questions against documents they are authorized to access (typically within assigned department scope).
- View their own query history and permitted document results.
- View their own dashboard.

**Restrictions**

- Cannot upload PDFs or add any data/files to the system.
- Cannot create, modify, or remove other users.
- Cannot manage departments or Admins.

## 6. Role Permission Matrix

| Capability | Super Admin | Admin | User |
|---|---|---|---|
| Sign in with Google | Yes | Yes | Yes |
| Auto-provisioned from `.env` email | Yes | No | No |
| Create Admin (name, email, department) | Yes | No | No |
| Create User (name, email) | Yes | Yes (own dept) | No |
| Assign/change User department | Yes | No | No |
| Upload documents / add data | Yes | Yes | **No** |
| Ask questions / query RAG | Yes | Yes | Yes |
| Cross-department visibility | Yes | No | No |
| Department-scoped admin visibility | Yes | Yes (own dept) | No |
| User-level visibility only | — | — | Yes |

## 7. Business Scope

### In Scope

- Google login/authentication.
- Environment-based Super Admin provisioning (`SUPER_ADMIN_EMAIL`).
- Custom role and department authorization.
- Super Admin Admin-creation flow (name, email, department name).
- Admin User-creation flow (name, email).
- Super Admin cross-department user assignment and department changes.
- PDF ingestion restricted to Super Admin and Admin.
- Query access for Super Admin, Admin, and User.
- PDF ingestion for normal and scanned PDFs.
- Extraction of text, tables, images, graphs and related content.
- Parent-child chunking.
- Dense embeddings.
- Qdrant vector storage.
- BM25 sparse retrieval.
- Hybrid retrieval and RRF ranking.
- Vision-capable Qwen answer generation through Groq.
- User/department data isolation.
- Admin dashboards.
- Logging, tracing, and metrics.
- Microservice architecture.
- Docker Compose deployment.

### Out of Scope for the Baseline

The supplied requirements do not define non-PDF file ingestion, fine-tuning of the LLM, autonomous agent workflows, external knowledge search, or advanced document editing. These should be treated as future extensions unless separately approved.

## 8. Business-Level Requirements

| ID | Requirement | Priority |
|---|---|---|
| BR-001 | The system shall provision exactly one environment-defined Super Admin from `SUPER_ADMIN_EMAIL`. | Must |
| BR-002 | The Super Admin shall create Admins using name, email, and department name. | Must |
| BR-003 | The Super Admin shall assign any User to any department and change User department assignments. | Must |
| BR-004 | The Admin shall create Users using name and email within the authorized department. | Must |
| BR-005 | Only Super Admin and Admin shall upload documents or add data to the system. | Must |
| BR-006 | Super Admin, Admin, and User shall be able to ask questions against authorized documents. | Must |
| BR-007 | User shall not upload documents or add data to the system. | Must |
| BR-008 | The system shall process both normal and scanned PDFs. | Must |
| BR-009 | The system shall preserve information from text, tables, images, graphs, and other extracted document elements. | Must |
| BR-010 | Retrieval shall combine sparse and dense signals. | Must |
| BR-011 | The final retrieval ranking shall use RRF. | Must |
| BR-012 | The answer-generation model shall support multimodal input. | Must |
| BR-013 | Google authentication shall be used for login. | Must |
| BR-014 | Departmental authorization shall restrict access to data. | Must |
| BR-015 | Super Admin shall have cross-department visibility. | Must |
| BR-016 | Admin shall have department-level visibility only. | Must |
| BR-017 | User shall have user-level visibility only. | Must |
| BR-018 | The solution shall implement logging, tracing, and metrics. | Must |
| BR-019 | The solution shall be implemented using microservices. | Must |
| BR-020 | Services shall be containerized using Docker Compose. | Must |

## 9. Success Measures

The following measures are recommended implementation KPIs because numerical targets were not defined in the supplied requirements:

- Document ingestion success rate.
- Extraction success rate by document type.
- Retrieval relevance / Recall@K / MRR or NDCG on a curated evaluation set.
- Grounded-answer rate.
- Citation/source-attribution coverage where implemented.
- End-to-end query latency.
- P95 ingestion and query latency.
- Authorization violation rate: target zero.
- Upload attempts blocked for User role: target 100% enforcement.
- Service availability and error rate.
- Trace/log completeness for ingestion and query workflows.

## 10. Key Business Risks and Mitigations

| Risk | Impact | Recommended Mitigation |
|---|---|---|
| Complex scanned PDFs | Missing or distorted content | Validate Docling extraction quality with representative documents; add OCR fallback if required |
| Tables/graphs lose structure | Incorrect answers | Store element metadata, page information, hierarchy, and references to original artifacts |
| Dense retrieval misses exact terms | Poor retrieval | Keep BM25 as a complementary sparse retriever and combine with RRF |
| Incorrect cross-user access | High security risk | Enforce authorization in every service/API that accesses user or document data |
| User uploads unauthorized data | Data governance breach | Block upload APIs for User role server-side; hide upload UI for Users |
| Large document ingestion | High latency/resource consumption | Async ingestion jobs, queue-based processing, progress status, retries |
| LLM hallucination | Incorrect business answers | Ground prompts on retrieved evidence, preserve source metadata, implement evaluation and answer constraints |
| Dependency/provider outage | Reduced availability | Provider abstraction, timeout/retry handling, health checks, and failure states |
| Super Admin email misconfiguration | Lockout or wrong provisioning | Document `.env` setup; validate on startup; audit first-login provisioning |

## 11. High-Level Business Workflow

### 11.1 Bootstrap

1. Platform operator sets `SUPER_ADMIN_EMAIL` in `.env`.
2. Super Admin signs in with Google using the configured email.
3. System auto-provisions Super Admin account on first login.

### 11.2 Administration

1. Super Admin creates an Admin by entering name, email, and department name.
2. System creates the department if needed and assigns the Admin.
3. Admin signs in with Google.
4. Admin adds Users by entering name and email (within own department).
5. Super Admin may assign any User to any department or change department assignment.

### 11.3 Data Ingestion (Super Admin / Admin only)

1. Super Admin or Admin uploads a PDF.
2. Ingestion service stores the source file and creates an ingestion job.
3. Extraction service processes the PDF using Docling.
4. Chunking/indexing service creates parent-child chunks and metadata.
5. Embedding service generates dense vectors.
6. Vector/sparse indexing stores retrievable representations.

### 11.4 Query (Super Admin / Admin / User)

1. Authenticated user submits a question.
2. Authorization service determines permitted document scope by role and department.
3. Retrieval service performs BM25 + dense retrieval with authorization filters.
4. RRF combines the retrieval results.
5. Context assembly prepares text, table, image, graph, and metadata evidence.
6. Qwen through Groq generates the answer using the retrieved context.
7. The response and operational telemetry are stored/logged as appropriate.

## 12. Assumptions and Open Decisions

The supplied requirements establish the architecture direction, but the following implementation decisions should be finalized during solution design:

- Whether documents are stored in object storage and which provider is used.
- Exact Google embedding model/version.
- Exact Qwen model/version exposed by Groq.
- Whether BM25 is computed from normalized document text, extracted element text, or another representation.
- How image/graph elements are passed to the vision model.
- Whether chat history is persisted.
- Retention and deletion policies for documents and query history.
- Exact dashboard KPIs.
- Whether one Admin can manage multiple departments.
- Whether Users can belong to multiple departments simultaneously.
- API gateway and service-to-service authentication mechanism.
- Whether Super Admin can create multiple Admins for the same department.

## 13. Recommendation

Proceed with a vertical-slice MVP first: environment-based Super Admin provisioning -> Google authentication -> Admin/User authorization -> PDF upload (Super Admin/Admin only) -> Docling extraction -> parent-child indexing -> Qdrant + BM25 -> RRF retrieval -> Qwen answer generation (all roles) -> role-aware dashboard. Once this flow is stable, add production-grade observability, scaling, evaluation, retries, and administrative analytics.
