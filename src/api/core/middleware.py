from uuid6 import uuid7
import time
from collections.abc import Awaitable, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimiterMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        return await call_next(request)

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Custom middleware to add request id to request"""
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
       
       # Generate unique request id per http request    
       request_id = str(uuid7())

       request.state.request_id = request_id
       response: Response = await call_next(request)
       response.headers["X-Request-ID"] = request_id

       return response


class LoggingMidderware(BaseHTTPMiddleware):
    async def dispatch(
        self, request:Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        return await call_next(request)

        
MIDDLEWARE_STACK: list[type[BaseHTTPMiddleware]] = [
    RateLimiterMiddleware,
    RequestIDMiddleware,
    LoggingMidderware,
    # ErrorHandlingMiddleware
]

MIDDLEWARE_STACK.reverse()