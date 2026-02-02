"""Global exception handlers for FastAPI application."""

from exceptions import (
    CSVParseError,
    GmailAuthError,
    InvalidCredentialsError,
    RecipientNotFoundError,
    TemplateNotFoundError,
    UserNotFoundError,
    ValidationError,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Map exception types to HTTP status codes
EXCEPTION_STATUS_CODES: dict[type[Exception], int] = {
    UserNotFoundError: 404,
    RecipientNotFoundError: 404,
    TemplateNotFoundError: 404,
    ValidationError: 409,
    GmailAuthError: 400,
    InvalidCredentialsError: 400,
    CSVParseError: 400,
    ValueError: 400,
}


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""

    for exc_class, status_code in EXCEPTION_STATUS_CODES.items():

        @app.exception_handler(exc_class)
        async def handler(request: Request, exc: Exception, status_code: int = status_code):
            return JSONResponse(status_code=status_code, content={"detail": str(exc)})
