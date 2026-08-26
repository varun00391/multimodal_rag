from rag_shared.models.enums import DocumentStatus, IngestionJobStatus


def map_job_status_to_document_status(status: IngestionJobStatus) -> DocumentStatus:
    mapping = {
        IngestionJobStatus.QUEUED: DocumentStatus.QUEUED,
        IngestionJobStatus.EXTRACTING: DocumentStatus.EXTRACTING,
        IngestionJobStatus.CHUNKING: DocumentStatus.CHUNKING,
        IngestionJobStatus.EMBEDDING: DocumentStatus.EMBEDDING,
        IngestionJobStatus.INDEXING: DocumentStatus.INDEXING,
        IngestionJobStatus.COMPLETED: DocumentStatus.READY,
        IngestionJobStatus.FAILED: DocumentStatus.FAILED_INDEXING,
    }
    return mapping.get(status, DocumentStatus.QUEUED)
