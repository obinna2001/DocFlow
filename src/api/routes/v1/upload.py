from typing import Annotated
from fastapi import APIRouter, UploadFile, Depends, Request, status

from src.schemas.input import StatusCode
from src.schemas.translator import TranslationRequest
from src.services.logging import create_logger
from src.services.document import validate_document, save_uploaded_file
from src.services.extractor import pdf_text_extractor
from src.api.core.response import CustomJSONResponse

logger = create_logger()

# Initialise router
upload_router = APIRouter()


@upload_router.post("/document/upload")
async def upload_document(
    document: Annotated[UploadFile, Depends(validate_document)],
    language: TranslationRequest,
    request: Request
) -> CustomJSONResponse:
    request_id = getattr(request.state, "request_id", "N/A")
    logger.info(f"{request_id} upload in progress...")

    file_path = await save_uploaded_file(document, request)
    _ = pdf_text_extractor(file_path)  # type: ignore
    response_status = {
        "status": "success",
        "result": {
            "message": StatusCode.SUCCESSFUL_UPLOAD,
        },
        "requestID": request_id,
        "path": request.url.path
    }

    return CustomJSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_status
    )
