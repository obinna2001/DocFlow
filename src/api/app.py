import uvicorn
from typing import cast
from starlette.types import ExceptionHandler
from fastapi import FastAPI

from src.api.core.middleware import MIDDLEWARE_STACK
from src.api.routes.v1.upload import upload_router
from src.api.routes.v1.status import status_router
from src.api.core.exception import BaseAPIError, internal_api_error_handler, unhandled_exception_handler


description = """
DocFlow API helps you to translate documents from one language to another.

## Items
You can upload document and download the translated version

## Users
You will be able to:

* **Upload document** (currently in implementation)
* **Download document** (not implemented)
"""

app = FastAPI(
    title="DocFlow",
    description= description,
    version="0.0.1",
    contact={
        "name": "Okey Obinna",
        "contact": "okeyobinna2001@gmail.com"
    }

)

for middleware_ in MIDDLEWARE_STACK:
    app.add_middleware(middleware_)

app.include_router(upload_router)
app.include_router(status_router)

# Project customer expection handlers as starletter ExceptionHandler type
# to prevent type checker error
app.add_exception_handler(BaseAPIError, cast(ExceptionHandler, internal_api_error_handler))
app.add_exception_handler(Exception, unhandled_exception_handler)

if __name__ == "__main__":
    uvicorn.run(
        "src.api.app:app", 
        port=8080, 
        reload=True
    )