from enum import StrEnum


class ErrorCode(StrEnum):
    UPLOAD_INVALID = "upload_invalid"
    INTERNAL_SERVER_ERROR = "internal_server_error"
    DECRYPTION_FAILED = "pdf_decryption_failed"
    PERMISSION_ERROR = "permission_not_granted"

    
class StatusCode(StrEnum):
    PENDING = "document_extraction_pending"
    PROCESSING = "document_extraction_processing"
    SUCCESS = "document_extraction_successful"
    FAILED = "document_extraction_failed"
    RETRYING = "retrying_document_extraction_process"

    SUCCESSFUL_UPLOAD = "file_upload_successful"

