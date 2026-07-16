from pathlib import Path 
import pytest


test_file = Path("/data/test_documentTrier.pdf")


@pytest.mark.anyio
async def test_upload_document(async_client):
    """test_upload_document tests the upload_document POST endpoint in DocFlow"""
    request = {

    }
    response = await async_client.post("/document/upload", request)
    assert response.status_code == 200

