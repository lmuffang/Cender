"""Dependency injection factories for FastAPI endpoints."""

from sqlalchemy.orm import Session

from database import SessionLocal
from services.user_service import UserService
from services.template_service import TemplateService
from services.recipient_service import RecipientService
from services.email_service import EmailService
from services.gmail_auth_service import GmailAuthService


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_user_service(db: Session) -> UserService:
    """UserService factory."""
    return UserService(db)


def get_template_service(db: Session) -> TemplateService:
    """TemplateService factory."""
    return TemplateService(db)


def get_recipient_service(db: Session) -> RecipientService:
    """RecipientService factory."""
    return RecipientService(db)


def get_email_service(db: Session) -> EmailService:
    """EmailService factory."""
    return EmailService(db)


def get_gmail_auth_service(user_id: int) -> GmailAuthService:
    """GmailAuthService factory."""
    return GmailAuthService(user_id)
