import os
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def authenticate_gmail(credentials_path: str, token_path: str):
    """Authenticate with Gmail API"""
    creds = None
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    
    return build("gmail", "v1", credentials=creds)


def create_message(to_email: str, salutation: str, company: str, template: str, resume_path: str, subject: str):
    """Create email message with attachment"""
    msg = MIMEMultipart()
    msg["To"] = to_email
    msg["Subject"] = subject
    
    body = template.format(salutation=salutation, company=company)
    msg.attach(MIMEText(body, "plain"))
    
    with open(resume_path, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={os.path.basename(resume_path)}"
        )
        msg.attach(part)
    
    raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw_msg}, body


def send_email(service, message: dict, recipient: str):
    """Send email using Gmail API"""
    try:
        service.users().messages().send(userId="me", body=message).execute()
        print(f"Email sent to {recipient}")
    except HttpError as error:
        print(f"Failed to send email to {recipient}: {error}")
        raise error