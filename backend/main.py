import os
import json
import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, EmailStr, ConfigDict
import pandas as pd
from sqlalchemy.orm import Session

from database import engine, SessionLocal, Base, User, EmailLog, Template, EmailStatus, Recipient, user_recipients
from gmail_service import authenticate_gmail, create_message, send_email
import gender_guesser.detector as gender

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CV Email Sender API")

# CORS - Use environment variable for allowed origins in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

gender_detector = gender.Detector()

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
    created_at: datetime.datetime
    updated_at: datetime.datetime

class TemplateUpdate(BaseModel):
    content: str

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


# Helper functions
def guess_salutation(first_name: str | None) -> str:
    """Guess salutation based on first name"""
    if not first_name:
        return "Monsieur"
    g = gender_detector.get_gender(first_name)
    if g in ("male", "mostly_male"):
        return "Monsieur"
    elif g in ("female", "mostly_female"):
        return "Madame"
    return "Monsieur"


def get_credentials_path(user_id: int) -> str:
    """Get credentials file path for user"""
    return f"./credentials/user_{user_id}_credentials.json"


def get_token_path(user_id: int) -> str:
    """Get token file path for user"""
    return f"./credentials/user_{user_id}_token.json"


def get_resume_path(user_id: int) -> str:
    """Get resume file path for user"""
    return f"./data/user_{user_id}_resume.pdf"


def send_emails_stream(
    *,
    user_id: int,
    recipient_ids: list[int],
    subject: str,
    template: str,
    dry_run: bool,
    db: Session,
):
    """Stream email sending process"""
    # Verify user
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        yield json.dumps({"error": "User not found"}) + "\n"
        return

    credentials_path = get_credentials_path(user_id)
    resume_path = get_resume_path(user_id)

    if not os.path.exists(credentials_path):
        yield json.dumps({"error": "Gmail credentials not uploaded"}) + "\n"
        return

    if not os.path.exists(resume_path):
        yield json.dumps({"error": "Resume not uploaded"}) + "\n"
        return

    # Get recipients by IDs
    recipients = db.query(Recipient).filter(Recipient.id.in_(recipient_ids)).all()
    if not recipients:
        yield json.dumps({"error": "No valid recipients found"}) + "\n"
        return

    # Get already sent emails for this user
    # Kinda duplicate of sent_emails
    sent_recipient_ids = {
        log.recipient_id
        for log in db.query(EmailLog)
        .filter(
            EmailLog.user_id == user_id,
            EmailLog.status == EmailStatus.SENT,
            EmailLog.recipient_id.isnot(None)
        )
        .all()
    }
    sent_emails = {
        log.recipient_email
        for log in db.query(EmailLog)
        .filter(
            EmailLog.user_id == user_id,
            EmailLog.status == EmailStatus.SENT
        )
        .all()
    }

    service = None
    if not dry_run:
        service = authenticate_gmail(credentials_path, get_token_path(user_id))

    for recipient in recipients:
        email = recipient.email
        recipient_id = recipient.id

        # Check if already sent
        if recipient_id in sent_recipient_ids or email in sent_emails:
            yield json.dumps({
                "recipient_id": recipient_id,
                "email": email,
                "status": EmailStatus.SKIPPED,
                "message": "Already sent"
            }) + "\n"
            continue

        try:
            first_name = recipient.first_name or ""
            last_name = recipient.last_name or ""
            salutation_text = guess_salutation(first_name)
            if last_name:
                salutation = f"{salutation_text} {last_name}".strip()
            else:
                salutation = salutation_text

            company = recipient.company or ""

            msg, body = create_message(
                email,
                salutation,
                company,
                template,
                resume_path,
                subject,
            )

            if dry_run:
                yield json.dumps({
                    "recipient_id": recipient_id,
                    "email": email,
                    "status": "dry_run",
                    "preview": body,
                }) + "\n"
            else:
                send_email(service, msg, email)

                log = EmailLog(
                    user_id=user_id,
                    recipient_id=recipient_id,
                    recipient_email=email,
                    subject=subject,
                    status=EmailStatus.SENT,
                    sent_at=datetime.datetime.now(datetime.timezone.utc),
                )
                db.add(log)
                db.commit()

                yield json.dumps({
                    "recipient_id": recipient_id,
                    "email": email,
                    "status": "sent",
                    "message": "Email sent",
                }) + "\n"

        except Exception as e:
            error_msg = str(e)
            if not dry_run:
                log = EmailLog(
                    user_id=user_id,
                    recipient_id=recipient_id,
                    recipient_email=email,
                    subject=subject,
                    status=EmailStatus.FAILED,
                    sent_at=datetime.datetime.now(datetime.timezone.utc),
                    error_message=error_msg,
                )
                db.add(log)
                db.commit()

            yield json.dumps({
                "recipient_id": recipient_id,
                "email": email,
                "status": "failed",
                "message": error_msg,
            }) + "\n"


# ============================================================================
# ROOT
# ============================================================================
@app.get("/")
async def root():
    return {"message": "CV Email Sender API"}


# ============================================================================
# USERS CRUD
# ============================================================================
@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=409, detail=f"User with email {user.email} already exists!")
    new_user = User(username=user.username, email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@app.get("/users/", response_model=list[UserResponse])
async def list_users(db: Session = Depends(get_db)):
    """List all users"""
    return db.query(User).all()


@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ============================================================================
# USER-SPECIFIC RESOURCES (Credentials, Resume)
# ============================================================================
@app.post("/users/{user_id}/credentials")
async def upload_credentials(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload Gmail credentials for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    os.makedirs("./credentials", exist_ok=True)
    credentials_path = get_credentials_path(user_id)
    
    with open(credentials_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"message": "Credentials uploaded successfully"}


@app.post("/users/{user_id}/resume")
async def upload_resume(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload resume PDF for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not file.filename or not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    os.makedirs("./data", exist_ok=True)
    resume_path = get_resume_path(user_id)
    
    with open(resume_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"message": "Resume uploaded successfully"}


# ============================================================================
# TEMPLATES CRUD
# ============================================================================
@app.get("/users/{user_id}/template", response_model=TemplateResponse)
async def get_template(user_id: int, db: Session = Depends(get_db)):
    """Get user's template or return default"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    template = user.template
    if template:
        return template
    
    # Return default template info (not saved in DB)
    default_content = "Bonjour {salutation},\n\nJe me permets de vous contacter concernant une opportunité au sein de {company}. Vous trouverez ci-joint mon CV.\n\nCordialement,\nVotre Nom"
    # Create a temporary template object for response
    return TemplateResponse(
        id=0,
        user_id=user_id,
        content=default_content,
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc)
    )


@app.post("/users/{user_id}/template", response_model=TemplateResponse)
async def create_or_update_template(user_id: int, template_update: TemplateUpdate, db: Session = Depends(get_db)):
    """Create or update user's template"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    template = user.template
    if template:
        template.content = template_update.content
    else:
        template = Template(user_id=user_id, content=template_update.content)
        db.add(template)
    
    db.commit()
    db.refresh(template)
    return template


@app.put("/users/{user_id}/template", response_model=TemplateResponse)
async def update_template(user_id: int, template_update: TemplateUpdate, db: Session = Depends(get_db)):
    """Update user's template (alias for POST)"""
    return await create_or_update_template(user_id, template_update, db)


# ============================================================================
# RECIPIENTS CRUD
# ============================================================================
@app.post("/recipients/", response_model=RecipientResponse)
async def create_recipient(recipient: RecipientCreate, db: Session = Depends(get_db)):
    """Create a new recipient"""
    existing = db.query(Recipient).filter(Recipient.email == recipient.email).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Recipient with email {recipient.email} already exists")
    
    new_recipient = Recipient(
        email=recipient.email,
        first_name=recipient.first_name,
        last_name=recipient.last_name,
        company=recipient.company,
    )
    db.add(new_recipient)
    db.commit()
    db.refresh(new_recipient)
    return new_recipient


@app.get("/recipients/{recipient_id}", response_model=RecipientResponse)
async def get_recipient(recipient_id: int, db: Session = Depends(get_db)):
    """Get a specific recipient"""
    recipient = db.query(Recipient).filter(Recipient.id == recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    return recipient


@app.get("/users/{user_id}/recipients", response_model=list[RecipientResponse])
async def list_recipients(
    user_id: int,
    used: bool | None = Query(None, description="Filter by usage status"),
    db: Session = Depends(get_db),
):
    """List recipients for a user, optionally filtered by usage"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Base query: recipients linked to user
    query = (
        db.query(Recipient)
        .join(user_recipients)
        .filter(user_recipients.c.user_id == user_id)
    )

    if used is not None:
        # Subquery for sent emails
        sent_subquery = (
            db.query(EmailLog.recipient_id)
            .filter(
                EmailLog.user_id == user_id,
                EmailLog.status == EmailStatus.SENT,
                EmailLog.recipient_id.isnot(None)
            )
            .subquery()
        )
        
        if used:
            query = query.filter(Recipient.id.in_(db.query(sent_subquery.c.recipient_id)))
        else:
            query = query.filter(~Recipient.id.in_(db.query(sent_subquery.c.recipient_id)))

    recipients = query.all()
    return recipients


@app.post("/users/{user_id}/recipients-csv")
async def import_recipients_csv(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Parse CSV and create/merge recipients for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        content = await file.read()
        df = pd.read_csv(pd.io.common.BytesIO(content), dtype=str)

        created = 0
        updated = 0
        linked = 0

        for _, row in df.iterrows():
            email = (row.get("Email") or "").strip().lower()
            if not email:
                continue

            first_name = (row.get("First Name") or "").strip()
            last_name = (row.get("Last Name") or "").strip()
            company = row.get("Company", "")
            if isinstance(company, float): # can be NaN if empty
                company = ""
            company = company.strip()

            # Find existing recipient
            recipient = (
                db.query(Recipient)
                .filter(Recipient.email == email)
                .one_or_none()
            )

            if recipient:
                # Merge missing info only
                changed = False
                if first_name and not recipient.first_name:
                    recipient.first_name = first_name
                    changed = True
                if last_name and not recipient.last_name:
                    recipient.last_name = last_name
                    changed = True
                if company and not recipient.company:
                    recipient.company = company
                    changed = True
                if changed:
                    updated += 1
            else:
                # Create new recipient
                recipient = Recipient(
                    email=email,
                    first_name=first_name or None,
                    last_name=last_name or None,
                    company=company or None,
                )
                db.add(recipient)
                db.flush()  # assign id
                created += 1

            # Link recipient to user if not already linked
            if recipient not in user.recipients:
                user.recipients.append(recipient)
                linked += 1

        db.commit()

        return {
            "created": created,
            "updated": updated,
            "linked": linked,
            "total": created + updated,
        }

    except Exception as e:
        import traceback
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Error parsing CSV: {str(e)}: {traceback.format_exc()}",
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
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    recipient = db.query(Recipient).filter(Recipient.id == recipient_id).first()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")
    
    # Check if recipient is linked to user
    if recipient not in user.recipients:
        raise HTTPException(status_code=403, detail="Recipient not linked to user")
    
    # Get user's template
    template = user.template
    if not template:
        raise HTTPException(status_code=404, detail="User template not found. Please save a template first.")
    
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


@app.post("/users/{user_id}/send-emails/stream")
async def send_emails_endpoint(
    user_id: int,
    request: SendEmailsRequest,
    db: Session = Depends(get_db),
):
    """Send emails to selected recipients (streaming response)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's template
    template = user.template
    if not template:
        raise HTTPException(status_code=404, detail="User template not found. Please save a template first.")
    
    return StreamingResponse(
        send_emails_stream(
            user_id=user_id,
            recipient_ids=request.recipient_ids,
            subject=request.subject,
            template=template.content,
            dry_run=request.dry_run,
            db=db,
        ),
        media_type="text/event-stream",
    )


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
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    query = db.query(EmailLog).filter(EmailLog.user_id == user_id)
    
    if status:
        query = query.filter(EmailLog.status == status)
    
    logs = query.order_by(EmailLog.sent_at.desc()).limit(limit).all()
    return logs


@app.get("/users/{user_id}/stats")
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    """Get statistics for a user"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    total_sent = db.query(EmailLog).filter(
        EmailLog.user_id == user_id,
        EmailLog.status == EmailStatus.SENT
    ).count()
    
    total_failed = db.query(EmailLog).filter(
        EmailLog.user_id == user_id,
        EmailLog.status == EmailStatus.FAILED
    ).count()
    
    total_skipped = db.query(EmailLog).filter(
        EmailLog.user_id == user_id,
        EmailLog.status == EmailStatus.SKIPPED
    ).count()
    
    return {
        "total_sent": total_sent,
        "total_failed": total_failed,
        "total_skipped": total_skipped,
        "total_emails": total_sent + total_failed + total_skipped
    }


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
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not all and not recipient_id and not status and not before_date:
        raise HTTPException(
            status_code=400,
            detail="Must specify at least one filter (recipient_id, status, before_date) or set all=true"
        )
    
    query = db.query(EmailLog).filter(EmailLog.user_id == user_id)
    
    if recipient_id:
        query = query.filter(EmailLog.recipient_id == recipient_id)
    
    if status:
        query = query.filter(EmailLog.status == status)
    
    if before_date:
        try:
            date_obj = datetime.datetime.strptime(before_date, "%Y-%m-%d").replace(tzinfo=datetime.timezone.utc)
            query = query.filter(EmailLog.sent_at < date_obj)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    logs_to_delete = query.all()
    count = len(logs_to_delete)
    
    for log in logs_to_delete:
        db.delete(log)
    
    db.commit()
    
    return {
        "message": f"Deleted {count} email log(s)",
        "deleted_count": count
    }


@app.delete("/users/{user_id}/email-logs/{log_id}")
async def delete_email_log(user_id: int, log_id: int, db: Session = Depends(get_db)):
    """Delete a specific email log"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    log = db.query(EmailLog).filter(
        EmailLog.id == log_id,
        EmailLog.user_id == user_id
    ).first()
    
    if not log:
        raise HTTPException(status_code=404, detail="Email log not found")
    
    db.delete(log)
    db.commit()
    
    return {"message": "Email log deleted successfully"}
