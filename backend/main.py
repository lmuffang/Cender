import json
import datetime
import traceback
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, ConfigDict
import pandas as pd
from sqlalchemy.orm import Session

from database import (
    engine,
    SessionLocal,
    Base,
    User,
    EmailLog,
    Template,
    EmailStatus,
    Recipient,
    user_recipients,
)
from config import settings
from utils.logger import logger
from exceptions import UserNotFoundError, RecipientNotFoundError, TemplateNotFoundError
from services.user_service import UserService
from services.template_service import TemplateService
from services.recipient_service import RecipientService
from services.email_service import EmailService
from services.gmail_auth_service import GmailAuthService
from utils.gender_detector import guess_salutation

app = FastAPI(title=settings.app_name, version=settings.app_version)


@app.on_event("startup")
def on_startup():
    # Create tables
    Base.metadata.create_all(bind=engine)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger.info(f"Starting {settings.app_name} v{settings.app_version}")


# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic Models
class UserCreate(BaseModel):
    username: str
    email: EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr


class RecipientCreate(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None


class RecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str | None
    last_name: str | None
    salutation: str | None
    company: str | None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    content: str
    subject: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class TemplateUpdate(BaseModel):
    content: str
    subject: str


class EmailPreview(BaseModel):
    email: str
    subject: str
    body: str


class EmailLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    recipient_id: int | None
    recipient_email: str
    subject: str
    status: str
    sent_at: datetime.datetime
    error_message: str | None


class SendEmailsRequest(BaseModel):
    recipient_ids: list[int]
    subject: str
    dry_run: bool = False


# Helper functions removed - now in service layer


# ============================================================================
# ROOT
# ============================================================================
@app.get("/")
async def root():
    return {"message": "Cender API"}


# ============================================================================
# USERS CRUD
# ============================================================================
@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    try:
        user_service = UserService(db)
        new_user = user_service.create(user.username, user.email)
        return new_user
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/users/", response_model=list[UserResponse])
async def list_users(db: Session = Depends(get_db)):
    """List all users"""
    user_service = UserService(db)
    return user_service.get_all()


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user"""
    try:
        user_service = UserService(db)
        return user_service.get_by_id(user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/users/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    Delete a user and all associated data.

    This will permanently delete:
    - User's email template
    - User's email logs
    - User's recipient links (recipients themselves are kept)
    - User's files (credentials, token, resume)
    """
    try:
        user_service = UserService(db)
        result = user_service.delete(user_id)
        return result
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================================
# USER-SPECIFIC RESOURCES (Credentials, Resume)
# ============================================================================
@app.post("/users/{user_id}/credentials")
async def upload_credentials(
    user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Upload Gmail credentials for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    gmail_service = GmailAuthService(user_id)
    content = await file.read()
    success, message = gmail_service.save_credentials(content)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {"message": message}


@app.get("/users/{user_id}/files-status")
async def get_files_status(user_id: int, db: Session = Depends(get_db)):
    """Check if user has uploaded credentials and resume"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    gmail_service = GmailAuthService(user_id)
    status = gmail_service.get_files_status()

    return {
        "has_credentials": status.has_credentials,
        "has_resume": status.has_resume,
    }


@app.get("/users/{user_id}/gmail-status")
async def get_gmail_status(user_id: int, db: Session = Depends(get_db)):
    """Check Gmail connection status for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    gmail_service = GmailAuthService(user_id)
    status = gmail_service.get_gmail_status()

    return {
        "connected": status.connected,
        "has_credentials": status.has_credentials,
        "has_token": status.has_token,
        "email": status.email,
        "error": status.error,
    }


@app.post("/users/{user_id}/gmail-auth-url")
async def get_gmail_auth_url(user_id: int, db: Session = Depends(get_db)):
    """
    Get OAuth authorization URL for manual flow.
    User should open this URL in their browser and paste the authorization code back.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    gmail_service = GmailAuthService(user_id)
    auth_url, error = gmail_service.get_auth_url()

    if error:
        raise HTTPException(status_code=400, detail=error)

    return {"auth_url": auth_url}


class GmailAuthCompleteRequest(BaseModel):
    auth_code: str


@app.post("/users/{user_id}/gmail-auth-complete")
async def complete_gmail_auth(
    user_id: int,
    request: GmailAuthCompleteRequest,
    db: Session = Depends(get_db)
):
    """
    Complete OAuth flow with authorization code.
    The user pastes the code they received after authorizing.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    gmail_service = GmailAuthService(user_id)
    success, message = gmail_service.complete_auth(request.auth_code)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"message": message}


@app.post("/users/{user_id}/gmail-disconnect")
async def disconnect_gmail(user_id: int, db: Session = Depends(get_db)):
    """
    Disconnect Gmail by removing the token.
    User will need to re-authorize to send emails.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    gmail_service = GmailAuthService(user_id)
    success, message = gmail_service.disconnect_gmail()

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"message": message}


@app.post("/users/{user_id}/resume")
async def upload_resume(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload resume PDF for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    gmail_service = GmailAuthService(user_id)
    content = await file.read()
    success, message = gmail_service.save_resume(content)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {"message": message}


# ============================================================================
# TEMPLATES CRUD
# ============================================================================
@app.get("/users/{user_id}/template", response_model=TemplateResponse)
async def get_template(user_id: int, db: Session = Depends(get_db)):
    """Get user's template or return default"""
    try:
        template_service = TemplateService(db)
        template_data = template_service.get_or_default(user_id)

        # Try to get actual template from DB
        try:
            template = template_service.get(user_id)
            return template
        except TemplateNotFoundError:
            # Return default template info (not saved in DB)
            return TemplateResponse(
                id=0,
                user_id=user_id,
                content=template_data["content"],
                subject=template_data["subject"],
                created_at=datetime.datetime.now(datetime.timezone.utc),
                updated_at=datetime.datetime.now(datetime.timezone.utc),
            )
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/users/{user_id}/template", response_model=TemplateResponse)
async def create_or_update_template(
    user_id: int, template_update: TemplateUpdate, db: Session = Depends(get_db)
):
    """Create or update user's template"""
    try:
        template_service = TemplateService(db)
        return template_service.create_or_update(user_id, template_update.content, template_update.subject)
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.put("/users/{user_id}/template", response_model=TemplateResponse)
async def update_template(
    user_id: int, template_update: TemplateUpdate, db: Session = Depends(get_db)
):
    """Update user's template (alias for POST)"""
    return await create_or_update_template(user_id, template_update, db)


# ============================================================================
# RECIPIENTS CRUD
# ============================================================================
@app.post("/recipients/", response_model=RecipientResponse)
async def create_recipient(recipient: RecipientCreate, db: Session = Depends(get_db)):
    """Create a new recipient"""
    try:
        recipient_service = RecipientService(db)
        return recipient_service.create(
            email=recipient.email,
            first_name=recipient.first_name,
            last_name=recipient.last_name,
            company=recipient.company,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/recipients/{recipient_id}", response_model=RecipientResponse)
async def get_recipient(recipient_id: int, db: Session = Depends(get_db)):
    """Get a specific recipient"""
    try:
        recipient_service = RecipientService(db)
        return recipient_service.get_by_id(recipient_id)
    except RecipientNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/users/{user_id}/recipients", response_model=list[RecipientResponse])
async def list_recipients(
    user_id: int,
    used: bool | None = Query(None, description="Filter by usage status"),
    db: Session = Depends(get_db),
):
    """List recipients for a user, optionally filtered by usage"""
    try:
        recipient_service = RecipientService(db)
        return recipient_service.get_by_user(user_id, used)
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/users/{user_id}/recipients-csv")
async def import_recipients_csv(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Parse CSV and create/merge recipients for a user"""
    try:
        user_service = UserService(db)
        user = user_service.get_by_id(user_id)
        recipient_service = RecipientService(db)

        content = await file.read()
        df = pd.read_csv(pd.io.common.BytesIO(content), dtype=str)

        created = 0
        updated = 0
        linked = 0

        for _, row in df.iterrows():
            email = row.get("Email", "")
            if not isinstance(email, str) or not email:
                continue  # is empty, NaN
            email = email.strip()
            recipient_data = {"First Name": "", "Last Name": "", "Company": ""}
            for key in recipient_data.keys():
                value = row.get(key)
                if not isinstance(value, str) or not value:
                    value = ""  # is empty, NaN
                recipient_data[key] = value.strip()

            # Find existing recipient
            recipient = db.query(Recipient).filter(Recipient.email == email).one_or_none()

            if recipient:
                # Merge missing info only
                changed = False
                keys_attribute_map = {
                    "First Name": "first_name",
                    "Last Name": "last_name",
                    "Company": "company",
                }
                for key, attribute in keys_attribute_map.items():
                    if recipient_data.get(key) and not getattr(recipient, attribute):
                        setattr(recipient, attribute, recipient_data.get(key))
                        changed = True
                if changed:
                    updated += 1
            else:
                # Create new recipient
                try:
                    recipient = recipient_service.create(
                        email=email,
                        first_name=recipient_data["First Name"] or None,
                        last_name=recipient_data["Last Name"] or None,
                        company=recipient_data["Company"] or None,
                    )
                    created += 1
                except ValueError:
                    # Recipient already exists (race condition)
                    recipient = db.query(Recipient).filter(Recipient.email == email).first()
                    updated += 1

            # Link recipient to user if not already linked
            if recipient not in user.recipients:
                recipient_service.link_to_user(user_id, recipient.id)
                linked += 1

        return {
            "created": created,
            "updated": updated,
            "linked": linked,
            "total": created + updated,
        }

    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error parsing CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing CSV: {str(e)}",
        )


# ============================================================================
# EMAIL OPERATIONS
# ============================================================================
@app.post("/users/{user_id}/preview-email/{recipient_id}", response_model=EmailPreview)
async def preview_email(
    user_id: int,
    recipient_id: int,
    subject: str = Form(...),
    db: Session = Depends(get_db),
):
    """Preview how an email will look for a specific recipient"""
    try:
        user_service = UserService(db)
        user = user_service.get_by_id(user_id)

        recipient_service = RecipientService(db)
        recipient = recipient_service.get_by_id(recipient_id)

        # Check if recipient is linked to user
        if recipient not in user.recipients:
            raise HTTPException(status_code=403, detail="Recipient not linked to user")

        # Get user's template
        template_service = TemplateService(db)
        template = template_service.get(user_id)

        # Generate preview
        first_name = recipient.first_name or ""
        last_name = recipient.last_name or ""
        salutation_text = guess_salutation(first_name)
        if last_name:
            salutation = f"{salutation_text} {last_name}".strip()
        else:
            salutation = salutation_text

        company = recipient.company or ""
        body = template.content.format(salutation=salutation, company=company)

        return EmailPreview(
            email=recipient.email,
            subject=subject,
            body=body,
        )
    except (UserNotFoundError, RecipientNotFoundError, TemplateNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/users/{user_id}/send-emails/stream")
async def send_emails_endpoint(
    user_id: int,
    request: SendEmailsRequest,
    db: Session = Depends(get_db),
):
    """Send emails to selected recipients (streaming response)"""
    try:
        email_service = EmailService(db)
        return StreamingResponse(
            email_service.send_emails_stream(
                user_id=user_id,
                recipient_ids=request.recipient_ids,
                subject=request.subject,
                dry_run=request.dry_run,
            ),
            media_type="text/event-stream",
        )
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================================
# EMAIL LOGS
# ============================================================================
@app.get("/users/{user_id}/email-logs", response_model=list[EmailLogResponse])
async def get_email_logs(
    user_id: int,
    limit: int = Query(100, ge=1, le=10000),
    status: EmailStatus | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get email sending history for a user"""
    try:
        email_service = EmailService(db)
        return email_service.get_logs(user_id, limit, status)
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/users/{user_id}/stats")
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    """Get statistics for a user"""
    try:
        email_service = EmailService(db)
        return email_service.get_stats(user_id)
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/users/{user_id}/email-logs")
async def delete_email_logs(
    user_id: int,
    recipient_id: int | None = Query(None, description="Delete logs for specific recipient"),
    status: EmailStatus | None = Query(None, description="Delete logs with specific status"),
    before_date: str | None = Query(None, description="Delete logs before this date (YYYY-MM-DD)"),
    all: bool = Query(False, description="Delete all logs for user"),
    db: Session = Depends(get_db),
):
    """Delete email logs for a user. Allows filtering by recipient, status, or date."""
    try:
        email_service = EmailService(db)
        return email_service.delete_logs(
            user_id=user_id,
            recipient_id=recipient_id,
            status=status,
            before_date=before_date,
            all_logs=all,
        )
    except UserNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/users/{user_id}/email-logs/{log_id}")
async def delete_email_log(user_id: int, log_id: int, db: Session = Depends(get_db)):
    """Delete a specific email log"""
    try:
        email_service = EmailService(db)
        email_service.delete_log(user_id, log_id)
        return {"message": "Email log deleted successfully"}
    except (UserNotFoundError, ValueError) as e:
        raise HTTPException(status_code=404, detail=str(e))
