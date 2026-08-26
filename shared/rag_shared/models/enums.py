import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    ADMIN = "ADMIN"
    USER = "USER"


class UserStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INDEXING = "INDEXING"
    READY = "READY"
    FAILED_EXTRACTION = "FAILED_EXTRACTION"
    FAILED_CHUNKING = "FAILED_CHUNKING"
    FAILED_EMBEDDING = "FAILED_EMBEDDING"
    FAILED_INDEXING = "FAILED_INDEXING"


class IngestionJobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    EXTRACTING = "EXTRACTING"
    CHUNKING = "CHUNKING"
    EMBEDDING = "EMBEDDING"
    INDEXING = "INDEXING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ElementType(str, enum.Enum):
    TEXT = "text"
    TABLE = "table"
    IMAGE = "image"
    GRAPH = "graph"
    OTHER = "other"
