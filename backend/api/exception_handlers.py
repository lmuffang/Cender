"""Global exception handlers for FastAPI application."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from exceptions import (
    UserNotFoundError,
    RecipientNotFoundError,
    TemplateNotFoundError,
    ValidationError,
    GmailAuthError,
    InvalidCredentialsError,
    CSVParseError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all global exception handlers on the FastAPI app."""

    @app.exception_handler(UserNotFoundError)
    async def user_not_found_handler(request: Request, exc: UserNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(RecipientNotFoundError)
    async def recipient_not_found_handler(request: Request, exc: RecipientNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(TemplateNotFoundError)
    async def template_not_found_handler(request: Request, exc: TemplateNotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(GmailAuthError)
    async def gmail_auth_error_handler(request: Request, exc: GmailAuthError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(InvalidCredentialsError)
    async def invalid_credentials_handler(request: Request, exc: InvalidCredentialsError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(CSVParseError)
    async def csv_parse_error_handler(request: Request, exc: CSVParseError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})
