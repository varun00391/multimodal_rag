from pydantic import BaseModel, EmailStr, Field

from app.schemas.enums import UserRole, UserStatus


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class UserResponse(BaseModel):
    user_id: str
    email: EmailStr
    name: str
    role: UserRole
    department_ids: list[str]
    status: UserStatus
    is_super_admin_seed: bool = False

    model_config = {"from_attributes": True}


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class DepartmentResponse(BaseModel):
    department_id: str
    name: str

    model_config = {"from_attributes": True}


class AdminCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr
    department_name: str = Field(min_length=1, max_length=255)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    email: EmailStr


class UserDepartmentUpdate(BaseModel):
    department_id: str


class UserStatusUpdate(BaseModel):
    status: UserStatus


class DocumentUploadResponse(BaseModel):
    document_id: str
    status: str
    ingestion_job_id: str


class DocumentResponse(BaseModel):
    document_id: str
    title: str
    filename: str
    status: str
    department_id: str
    owner_user_id: str
    size_bytes: int

    model_config = {"from_attributes": True}


class DocumentElementResponse(BaseModel):
    element_id: str
    document_id: str
    element_type: str
    page: int | None = None
    source_ref: str | None = None
    content: str | None = None


class IngestionJobResponse(BaseModel):
    job_id: str
    document_id: str
    status: str
    progress: int
    current_step: str | None = None


class RetrievalSearchRequest(BaseModel):
    query: str
    top_k_dense: int = 10
    top_k_sparse: int = 10
    final_top_k: int = 8
    document_ids: list[str] | None = None


class RetrievalResultItem(BaseModel):
    chunk_id: str
    document_id: str
    page: int | None = None
    element_type: str
    score: float
    retrieval_sources: list[str]


class RetrievalSearchResponse(BaseModel):
    results: list[RetrievalResultItem]


class QueryRequest(BaseModel):
    query: str
    document_ids: list[str] | None = None
    conversation_id: str | None = None


class QuerySource(BaseModel):
    document_id: str
    page: int | None = None
    chunk_id: str
    element_type: str


class QueryUsage(BaseModel):
    retrieved_chunks: int


class QueryResponse(BaseModel):
    query_id: str
    answer: str
    sources: list[QuerySource]
    usage: QueryUsage


class AuditLogResponse(BaseModel):
    id: str
    event_type: str
    resource_type: str | None = None
    resource_id: str | None = None
    created_at: str
