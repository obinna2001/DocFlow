from fastapi import APIRouter

from src.services.logging import create_logger


status_router = APIRouter()

logger = create_logger()


@status_router.get("/document/status")
async def get_document_extraction_status(
    application_id: str = "019e4164-c4e8-7d80-8ded-2c684163a1b4"
):
    id = application_id
    return {
        "error": False,
        "message": {
            "status": "Done",
            "message": f"Document extraction was successful for {id}"
        }
    }