"""Email sending and logging endpoints."""

import os

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from config import settings
from database import EmailStatus
from api.schemas import EmailPreview, EmailLogResponse, SendEmailsRequest
from api.dependencies import get_db, get_user_service, get_template_service, get_recipient_service, get_email_service
from gmail_service import safe_format_template
from utils.gender_detector import guess_salutation

router = APIRouter(prefix="/users/{user_id}", tags=["emails"])


@router.post("/preview-email/{recipient_id}", response_model=EmailPreview)
async def preview_email(
    user_id: int,
    recipient_id: int,
    subject: str = Form(...),
    db: Session = Depends(get_db),
):
    """Preview how an email will look for a specific recipient."""
    user_service = get_user_service(db)
    user = user_service.get_by_id(user_id)

    recipient_service = get_recipient_service(db)
    recipient = recipient_service.get_by_id(recipient_id)

    # Check if recipient is linked to user
    if recipient not in user.recipients:
        raise HTTPException(status_code=403, detail="Recipient not linked to user")

    # Get user's template
    template_service = get_template_service(db)
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
    body = safe_format_template(template.content, salutation=salutation, company=company, company_name=company)

    # Get resume filename if available
    resume_path = settings.get_resume_path(user_id)
    attachment_filename = os.path.basename(resume_path) if resume_path else None

    return EmailPreview(
        email=recipient.email,
        subject=subject,
        body=body,
        attachment_filename=attachment_filename,
    )


@router.post("/send-emails/stream")
async def send_emails_endpoint(
    user_id: int,
    request: SendEmailsRequest,
    db: Session = Depends(get_db),
):
    """Send emails to selected recipients (streaming response)."""
    email_service = get_email_service(db)
    return StreamingResponse(
        email_service.send_emails_stream(
            user_id=user_id,
            recipient_ids=request.recipient_ids,
            subject=request.subject,
            dry_run=request.dry_run,
        ),
        media_type="text/event-stream",
    )


@router.get("/email-logs", response_model=list[EmailLogResponse])
async def get_email_logs(
    user_id: int,
    limit: int = Query(100, ge=1, le=10000),
    status: EmailStatus | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get email sending history for a user."""
    email_service = get_email_service(db)
    return email_service.get_logs(user_id, limit, status)


@router.get("/stats")
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    """Get statistics for a user."""
    email_service = get_email_service(db)
    return email_service.get_stats(user_id)


@router.delete("/email-logs")
async def delete_email_logs(
    user_id: int,
    recipient_id: int | None = Query(None, description="Delete logs for specific recipient"),
    status: EmailStatus | None = Query(None, description="Delete logs with specific status"),
    before_date: str | None = Query(None, description="Delete logs before this date (YYYY-MM-DD)"),
    all: bool = Query(False, description="Delete all logs for user"),
    db: Session = Depends(get_db),
):
    """Delete email logs for a user. Allows filtering by recipient, status, or date."""
    email_service = get_email_service(db)
    return email_service.delete_logs(
        user_id=user_id,
        recipient_id=recipient_id,
        status=status,
        before_date=before_date,
        all_logs=all,
    )


@router.delete("/email-logs/{log_id}")
async def delete_email_log(user_id: int, log_id: int, db: Session = Depends(get_db)):
    """Delete a specific email log."""
    email_service = get_email_service(db)
    email_service.delete_log(user_id, log_id)
    return {"message": "Email log deleted successfully"}
