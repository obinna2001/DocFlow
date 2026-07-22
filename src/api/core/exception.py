# Custom Exception Class to catch API errors
from fastapi import status, Request

from src.api.core.response import CustomJSONResponse
from src.schemas.input import ErrorCode
from src.services.logging import create_logger

logger = create_logger()

class BaseAPIError(Exception):
    """Base exception class for API based errors"""
    def __init__(
        self, 
        message: str, 
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = ""
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class InvalidInputError(BaseAPIError):
    """
    Custom Error for invalid input document. The Default status code is 400 
    i.e "status_code"=status.HTTP_400_BAD_REQUEST
    """
    def __init__(
        self,
        details: str,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        message = f"Invalid file upload: {details}"
        super().__init__(
            message=message, 
            status_code=status_code,
            error_code=ErrorCode.UPLOAD_INVALID
        )

class PDFDecryptionError(BaseAPIError):
    """
    Custom Error to catch empty and wrong error password during PDF decryption. The Default status code is 400 
    """
    def __init__(
        self,
        details: str,
        status_code: int = status.HTTP_400_BAD_REQUEST
    ):
        super().__init__(
            message=details, 
            status_code=status_code,
            error_code=ErrorCode.DECRYPTION_FAILED
        )

class PDFPermissionError(BaseAPIError):
    """
    Custom Error to catch PDF permission issues during PDF decryption. The Default status code is 403 
    """
    def __init__(
        self,
        details: str,
        status_code: int = status.HTTP_403_FORBIDDEN
    ):
        super().__init__(
            message=details, 
            status_code=status_code,
            error_code=ErrorCode.PERMISSION_ERROR
        )


async def internal_api_error_handler(
    request: Request, 
    error: BaseAPIError
) -> CustomJSONResponse:
    """Handles all Internal API Exception raised in DocFlow which inherits 
    from BaseAPIError
    """
    response_content = {
        "status": "error",
        "error": {
            "message": error.message,
            "errorCode": error.error_code
        },
        "requestID": getattr(request.state, "request_id", "N/A"),
        "path": request.url.path
    }
    logger.error(str(error.message))
    return CustomJSONResponse(
        status_code=error.status_code,
        content=response_content,
        headers=None
    )

async def unhandled_exception_handler(request: Request, error: Exception) -> CustomJSONResponse:
    """"Handles all unhandled exceptions that are not instances of BaseAPIError"""
    response_content = {
        "status": "error",
        "error": {
            "message": "An unexpected error occurred. Please try again later.",
            "errorCode": ErrorCode.INTERNAL_SERVER_ERROR
        },
        "requestID": getattr(request.state, "request_id", "N/A"),
        "path": request.url.path
    }
    logger.exception(f"Unhandled exception")
    return CustomJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_content,
        headers=None
    )



