import os
import json
import datetime
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio
from pydantic import BaseModel, EmailStr
import pandas as pd
from sqlalchemy.orm import Session

from database import engine, SessionLocal, Base, User, EmailLog, Template
from gmail_service import authenticate_gmail, create_message, send_email
import gender_guesser.detector as gender

# Create tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="CV Email Sender API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # FIXME: not safe!!
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


# Models
class UserCreate(BaseModel):
    username: str
    email: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        orm_mode = True


class EmailRecipient(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    company: str


class EmailRequest(BaseModel):
    user_id: int
    subject: str
    template: str
    recipients: list[EmailRecipient]
    dry_run: bool = False


class EmailPreview(BaseModel):
    email: str
    subject: str
    body: str


# Helper functions
def guess_salutation(first_name: str) -> str:
    """Guess salutation based on first name"""
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
    subject: str,
    template: str,
    recipients: list,
    dry_run: bool,
    db: Session,
):
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

    sent_emails = {
        log.recipient_email
        for log in db.query(EmailLog)
        .filter(EmailLog.user_id == user_id, EmailLog.status == "sent")
        .all()
    }

    service = None
    if not dry_run:
        service = authenticate_gmail(credentials_path, get_token_path(user_id))

    for recipient in recipients:
        email = recipient["email"]

        if email in sent_emails:
            yield json.dumps({
                "email": email,
                "status": "skipped",
                "message": "Already sent"
            }) + "\n"
            continue

        try:
            salutation = f"{guess_salutation(recipient['first_name'])} {recipient['last_name']}".strip()

            msg, body = create_message(
                email,
                salutation,
                recipient["company"],
                template,
                resume_path,
                subject,
            )

            if dry_run:
                yield json.dumps({
                    "email": email,
                    "status": "dry_run",
                    "preview": body,
                }) + "\n"
            else:
                send_email(service, msg, email)

                log = EmailLog(
                    user_id=user_id,
                    recipient_email=email,
                    subject=subject,
                    status="sent",
                    sent_at=datetime.datetime.now(datetime.timezone.utc),
                )
                db.add(log)
                db.commit()

                yield json.dumps({
                    "email": email,
                    "status": "sent",
                    "message": "Email sent",
                }) + "\n"

        except Exception as e:
            if not dry_run:
                log = EmailLog(
                    user_id=user_id,
                    recipient_email=email,
                    subject=subject,
                    status="failed",
                    sent_at=datetime.datetime.now(datetime.timezone.utc),
                )
                db.add(log)
                db.commit()

            yield json.dumps({
                "email": email,
                "status": "failed",
                "message": str(e),
            }) + "\n"



# Endpoints
@app.get("/")
async def root():
    return {"message": "CV Email Sender API"}

#### Users ####
#Crud
@app.post("/users/", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
    # Check email is present
    if db.query(User).filter(User.email==user.email).first():
        raise HTTPException(status_code=409, detail=f"User with email {user.email} already exists!")
    new_user = User(username=user.username, email=user.email)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

#cRud
@app.get("/users/" , response_model=list[UserResponse])
async def list_users(db: Session = Depends(get_db)):
    """List all users"""
    return db.query(User).all()

# #cruD
# @app.delete("/users/{user_id}")


#### login gmail ####
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
    
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")
    
    os.makedirs("./data", exist_ok=True)
    resume_path = get_resume_path(user_id)
    
    with open(resume_path, "wb") as f:
        content = await file.read()
        f.write(content)
    
    return {"message": "Resume uploaded successfully"}


@app.get("/users/{user_id}/template")
async def get_template(user_id: int, db: Session = Depends(get_db)):
    """Get user's last used template or default"""
    template = db.query(Template).filter(Template.user_id == user_id).order_by(Template.updated_at.desc()).first()
    
    if template:
        return {"content": template.content}
    
    # Default template
    default = "Bonjour {salutation},\n\nJe me permets de vous contacter concernant une opportunité au sein de {company}. Vous trouverez ci-joint mon CV.\n\nCordialement,\nVotre Nom"
    return {"content": default}


@app.post("/users/{user_id}/template")
async def save_template(user_id: int, content: str = Form(...), db: Session = Depends(get_db)):
    """Save or update user's template"""
    template = db.query(Template).filter(Template.user_id == user_id).first()
    if template:
        template.content = content
        template.updated_at = datetime.datetime.now(datetime.timezone.utc)
    else:
        template = Template(user_id=user_id, content=content)
        db.add(template)
    
    db.commit()
    return {"message": "Template saved successfully"}


@app.post("/users/{user_id}/parse-csv")
async def parse_csv(user_id: int, file: UploadFile = File(...)):
    """Parse CSV file and return recipients"""
    try:
        content = await file.read()
        df = pd.read_csv(pd.io.common.BytesIO(content), dtype=str)
        
        recipients = []
        for _, row in df.iterrows():
            email = row.get("Email", "").strip()
            first_name = row.get("First Name", "").strip()
            last_name = row.get("Last Name", "").strip()
            company = row.get("Company", row.get("Company Name for Emails", "")).strip()
            
            if email and first_name and last_name:
                recipients.append({
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "company": company
                })
        
        return {"recipients": recipients}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error parsing CSV: {str(e)}")


@app.post("/preview-email")
async def preview_email(recipient: EmailRecipient, template: str = Form(...)):
    """Preview how an email will look"""
    salutation = f"{guess_salutation(recipient.first_name)} {recipient.last_name}".strip()
    body = template.format(salutation=salutation, company=recipient.company)
    
    return EmailPreview(
        email=recipient.email,
        subject="",
        body=body,
    )

@app.post("/send-emails/stream")
async def send_emails_endpoint(
    user_id: int = Form(...),
    subject: str = Form(...),
    template: str = Form(...),
    recipients_json: str = Form(...),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
):
    recipients = json.loads(recipients_json)

    return StreamingResponse(
        send_emails_stream(
            user_id=user_id,
            subject=subject,
            template=template,
            recipients=recipients,
            dry_run=dry_run,
            db=db,
        ),
        media_type="text/event-stream",
    )


# @app.post("/send-emails")
# async def send_emails_endpoint(
#     user_id: int = Form(...),
#     subject: str = Form(...),
#     template: str = Form(...),
#     recipients_json: str = Form(...),
#     dry_run: bool = Form(False),
#     background_tasks: BackgroundTasks = BackgroundTasks(),
#     db: Session = Depends(get_db),
# ):
#     """Send emails to recipients"""
    
#     # Verify user exists
#     user = db.query(User).filter(User.id == user_id).first()
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
    
#     # Check files exist
#     credentials_path = get_credentials_path(user_id)
#     resume_path = get_resume_path(user_id)
    
#     if not os.path.exists(credentials_path):
#         raise HTTPException(status_code=400, detail="Gmail credentials not uploaded")
    
#     if not os.path.exists(resume_path):
#         raise HTTPException(status_code=400, detail="Resume not uploaded")
    
#     # Parse recipients
#     recipients = json.loads(recipients_json)
    
#     # Get already sent emails
#     sent_emails = set(
#         log.recipient_email for log in 
#         db.query(EmailLog).filter(EmailLog.user_id == user_id, EmailLog.status == "sent").all()
#     )
    
#     results = []
    
#     if not dry_run:
#         # Authenticate
#         service = authenticate_gmail(credentials_path, get_token_path(user_id))
    
#     for recipient in recipients:
#         email = recipient["email"]
        
#         # Skip if already sent
#         if email in sent_emails:
#             results.append({
#                 "email": email,
#                 "status": "skipped",
#                 "message": "Already sent"
#             })
#             continue
        
#         try:
#             salutation = f"{guess_salutation(recipient['first_name'])} {recipient['last_name']}".strip()
#             msg, body = create_message(
#                 email,
#                 salutation,
#                 recipient["company"],
#                 template,
#                 resume_path,
#                 subject
#             )
            
#             if dry_run:
#                 results.append({
#                     "email": email,
#                     "status": "dry_run",
#                     "message": "Email would be sent",
#                     "preview": body
#                 })
#             else:
#                 send_email(service, msg, email)
                
#                 # Log to database
#                 log = EmailLog(
#                     user_id=user_id,
#                     recipient_email=email,
#                     subject=subject,
#                     status="sent",
#                     sent_at=datetime.datetime.now(datetime.timezone.utc)
#                 )
#                 db.add(log)
#                 db.commit()
                
#                 results.append({
#                     "email": email,
#                     "status": "sent",
#                     "message": "Email sent successfully"
#                 })
        
#         except Exception as e:
#             results.append({
#                 "email": email,
#                 "status": "failed",
#                 "message": str(e)
#             })
            
#             # Log failure
#             if not dry_run:
#                 log = EmailLog(
#                     user_id=user_id,
#                     recipient_email=email,
#                     subject=subject,
#                     status="failed",
#                     sent_at=datetime.datetime.now(datetime.timezone.utc)
#                 )
#                 db.add(log)
#                 db.commit()
    
#     return {"results": results}


@app.get("/users/{user_id}/email-logs")
async def get_email_logs(user_id: int, limit: int = 100, db: Session = Depends(get_db)):
    """Get email sending history for a user"""
    logs = db.query(EmailLog).filter(EmailLog.user_id == user_id).order_by(EmailLog.sent_at.desc()).limit(limit).all()
    return logs


@app.get("/users/{user_id}/stats")
async def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    """Get statistics for a user"""
    total_sent = db.query(EmailLog).filter(EmailLog.user_id == user_id, EmailLog.status == "sent").count()
    total_failed = db.query(EmailLog).filter(EmailLog.user_id == user_id, EmailLog.status == "failed").count()
    
    return {
        "total_sent": total_sent,
        "total_failed": total_failed,
        "total_emails": total_sent + total_failed
    }