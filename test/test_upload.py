import pytest
from pathlib import Path 

from src.schemas.input import StatusCode

test_file_path = Path(__file__).parent / "data" / "test_documentTrier.pdf"

@pytest.mark.anyio
async def test_upload_document(async_client):
    """test_upload_document tests the upload_document POST endpoint in DocFlow"""
    with test_file_path.open("rb") as test_file:
        response = await async_client.post(
            "/document/upload",
            files={"document": ("test_documentTrier.pdf", test_file)},
            data={
                "source_language": "",
                "target_language":"ig"
            }
        )
    
    response_body = response.json()
    assert response_body == {
        "status": "success",
        "result": {
            "message": StatusCode.SUCCESSFUL_UPLOAD,
        },
        "requestID": response.headers["X-Request-ID"],
        "path": "/document/upload"
    }

