import logging
import uuid
import contextvars
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# Context variable to hold the request ID for the duration of a request
request_id_var = contextvars.ContextVar("request_id", default="default")

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.request_id = request_id_var.get()
        return True

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Extract X-Request-ID from header or generate a new UUID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            request_id_var.reset(token)

def configure_logging():
    # Configure root logger to output structured log lines including the request ID
    handler = logging.StreamHandler()
    handler.addFilter(RequestIDFilter())
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(request_id)s] %(name)s - %(message)s"
    )
    handler.setFormatter(formatter)
    
    root_logger = logging.getLogger()
    # Clear existing handlers to avoid duplicate output
    root_logger.handlers = []
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
    
    # Set logger levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
