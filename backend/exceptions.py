"""Custom exception classes for the application."""


class CVEmailSenderError(Exception):
    """Base exception for Cender application."""

    pass


class UserNotFoundError(CVEmailSenderError):
    """Raised when a user is not found."""

    pass


class RecipientNotFoundError(CVEmailSenderError):
    """Raised when a recipient is not found."""

    pass


class TemplateNotFoundError(CVEmailSenderError):
    """Raised when a template is not found."""

    pass


class InvalidCredentialsError(CVEmailSenderError):
    """Raised when credentials are invalid or missing."""

    pass


class EmailSendError(CVEmailSenderError):
    """Raised when email sending fails."""

    pass


class CSVParseError(CVEmailSenderError):
    """Raised when CSV parsing fails."""

    pass


class ValidationError(CVEmailSenderError):
    """Raised for duplicate/conflict errors (409)."""

    pass


class GmailAuthError(CVEmailSenderError):
    """Raised for Gmail authentication failures."""

    pass
