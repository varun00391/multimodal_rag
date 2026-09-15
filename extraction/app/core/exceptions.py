class ExtractionError(Exception):
    code = "EXTRACTION_ERROR"

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        if code:
            self.code = code
        self.message = message


class CorruptPDFError(ExtractionError):
    code = "CORRUPT_PDF"


class UnsupportedPDFError(ExtractionError):
    code = "UNSUPPORTED_PDF"


class EncryptedPDFError(ExtractionError):
    code = "ENCRYPTED_PDF"


class FileTooLargeError(ExtractionError):
    code = "FILE_TOO_LARGE"


class InvalidUploadError(ExtractionError):
    code = "INVALID_UPLOAD"


class OCRFailedError(ExtractionError):
    code = "OCR_FAILED"


class TableExtractionFailedError(ExtractionError):
    code = "TABLE_EXTRACTION_FAILED"


class VLMTimeoutError(ExtractionError):
    code = "VLM_TIMEOUT"


class NotFoundError(ExtractionError):
    code = "NOT_FOUND"


class JobNotFoundError(NotFoundError):
    code = "JOB_NOT_FOUND"


class DocumentNotFoundError(NotFoundError):
    code = "DOCUMENT_NOT_FOUND"
