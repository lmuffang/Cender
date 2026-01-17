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


def get_authorization_url(credentials_path: str, redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob") -> tuple[str, InstalledAppFlow]:
    """
    Generate OAuth authorization URL.
    
    Args:
        credentials_path: Path to OAuth credentials JSON
        redirect_uri: Redirect URI (use 'urn:ietf:wg:oauth:2.0:oob' for manual copy/paste)
    
    Returns:
        Tuple of (authorization_url, flow object)
    """
    flow = InstalledAppFlow.from_client_secrets_file(
        credentials_path, 
        SCOPES,
        redirect_uri=redirect_uri
    )
    
    auth_url, _ = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Force consent screen to ensure refresh token
    )
    
    return auth_url, flow


def complete_authorization(credentials_path: str, auth_code: str, token_path: str, redirect_uri: str = "urn:ietf:wg:oauth:2.0:oob"):
    """
    Complete OAuth flow with authorization code.
    
    Args:
        credentials_path: Path to OAuth credentials JSON
        auth_code: Authorization code from user
        token_path: Path to save token
        redirect_uri: Redirect URI (must match the one used to get auth URL)
    
    Returns:
        Gmail service object
    """
    flow = InstalledAppFlow.from_client_secrets_file(
        credentials_path,
        SCOPES,
        redirect_uri=redirect_uri
    )
    
    flow.fetch_token(code=auth_code)
    creds = flow.credentials
    
    # Save credentials
    with open(token_path, "w") as token:
        token.write(creds.to_json())
    
    return build("gmail", "v1", credentials=creds)


def authenticate_gmail(credentials_path: str, token_path: str):
    """
    Authenticate with Gmail API using existing token.
    Raises exception if token doesn't exist or is invalid.

    Args:
        credentials_path: Path to OAuth credentials JSON
        token_path: Path to token file

    Returns:
        Gmail service object

    Raises:
        FileNotFoundError: If token file doesn't exist
        Exception: If token is invalid and can't be refreshed
    """
    if not os.path.exists(token_path):
        raise FileNotFoundError("Token file not found. Please complete OAuth authorization first.")

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed credentials
            with open(token_path, "w") as token:
                token.write(creds.to_json())
        else:
            raise Exception("Token is invalid and cannot be refreshed. Please re-authorize.")

    return build("gmail", "v1", credentials=creds)


def check_gmail_connection(credentials_path: str, token_path: str) -> dict:
    """
    Check Gmail connection status without raising exceptions.

    Args:
        credentials_path: Path to OAuth credentials JSON
        token_path: Path to token file

    Returns:
        dict with keys:
            - connected: bool
            - has_credentials: bool
            - has_token: bool
            - email: str or None (Gmail address if connected)
            - error: str or None
    """
    result = {
        "connected": False,
        "has_credentials": os.path.exists(credentials_path),
        "has_token": os.path.exists(token_path),
        "email": None,
        "error": None
    }

    if not result["has_credentials"]:
        result["error"] = "Credentials file not uploaded"
        return result

    if not result["has_token"]:
        result["error"] = "Not authorized yet - please complete OAuth flow"
        return result

    try:
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            else:
                result["error"] = "Token expired and cannot be refreshed"
                return result

        # Try to get user profile to verify connection
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        result["connected"] = True
        result["email"] = profile.get("emailAddress")

    except Exception as e:
        result["error"] = str(e)

    return result


def create_message(
    to_email: str, salutation: str, company: str, template: str, resume_path: str, subject: str
):
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
            "Content-Disposition", f"attachment; filename={os.path.basename(resume_path)}"
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