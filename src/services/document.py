from pathlib import Path
from typing import Annotated
import aiofiles
from fastapi import File, Request, UploadFile, status

from src.api.core.exception import InvalidInputError
from src.services.logging import create_logger

logger = create_logger()

ROOT: Path = Path(__file__).parent.parent.parent
TEMP_DB: str = "tempDB"
UPLOAD_DIR: Path = Path(ROOT, TEMP_DB)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

async def save_uploaded_file(uploaded_file: UploadFile, request: Request) -> Path:
    """
    This function saves the uploaded file to a specified destination folder and returns the path to the saved file.

    Args:
        uploaded_file (UploadFile): The file uploaded by the user, represented as an UploadFile object.
        request (Request): The FastAPI request object.

    Returns:
        file_path: The path to the saved file.
    """
    request_id = str(getattr(request.state, "request_id", "N/A"))
    file_extension = Path(uploaded_file.filename or " ").suffix.lower()
    file = request_id + file_extension

    file_path = UPLOAD_DIR / file
    
    logger.info("Saving uploaded file...")
    async with aiofiles.open(file_path, mode='wb') as save_file:
        content = await uploaded_file.read()
        await save_file.write(content)

    logger.info("%s saved successfully.", file)
    return file_path


async def validate_document(
    file: Annotated[UploadFile, File()],
) -> UploadFile:
    
    MAX_FILE_SIZE = 10
    logger.info("Validating uploaded document...")
    file_extension = Path(file.filename or " ").suffix.lower()

    if file_extension not in ['.pdf', '.doc', '.docx', '.txt']:
        raise InvalidInputError(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            details=f"Upload either a .pdf, .doc, .docx or .txt file"
        )

    # Read uploaded file to check size
    file_content = await file.read()
    file_size_mb = len(file_content)/1_000_000   # convert upload file size to megabyte

    # Check for empty file
    if file_size_mb == 0:
        raise InvalidInputError(
            status_code=status.HTTP_400_BAD_REQUEST,
            details=f"Empty file uploaded. Upload a valid document"
        )
    
    # Check for large file
    if file_size_mb > MAX_FILE_SIZE:
        raise InvalidInputError(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            details=f"File size exceeds limit. "
            f"File size must be less than or equal to {MAX_FILE_SIZE} MB"
        )
    
    await file.seek(0)
    logger.info("File validation successful. File size: %.2f MB.", file_size_mb)

    return file

