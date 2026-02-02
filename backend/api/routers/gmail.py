"""Gmail authentication and file management endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from api.dependencies import get_db, get_gmail_auth_service, get_user_service
from api.schemas import GmailAuthCompleteRequest

router = APIRouter(prefix="/users/{user_id}", tags=["gmail"])


@router.post("/credentials")
async def upload_credentials(
    user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    """Upload Gmail credentials for a user."""
    get_user_service(db).get_by_id(user_id)

    gmail_service = get_gmail_auth_service(user_id)
    content = await file.read()
    success, message = gmail_service.save_credentials(content)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {"message": message}


@router.get("/files-status")
async def get_files_status(user_id: int, db: Session = Depends(get_db)):
    """Check if user has uploaded credentials and resume."""
    get_user_service(db).get_by_id(user_id)

    gmail_service = get_gmail_auth_service(user_id)
    status = gmail_service.get_files_status()

    return {
        "has_credentials": status.has_credentials,
        "has_resume": status.has_resume,
    }


@router.get("/gmail-status")
async def get_gmail_status(user_id: int, db: Session = Depends(get_db)):
    """Check Gmail connection status for a user."""
    get_user_service(db).get_by_id(user_id)

    gmail_service = get_gmail_auth_service(user_id)
    status = gmail_service.get_gmail_status()

    return {
        "connected": status.connected,
        "has_credentials": status.has_credentials,
        "has_token": status.has_token,
        "email": status.email,
        "error": status.error,
    }


@router.post("/gmail-auth-url")
async def get_gmail_auth_url(user_id: int, db: Session = Depends(get_db)):
    """
    Get OAuth authorization URL for manual flow.
    User should open this URL in their browser and paste the authorization code back.
    """
    get_user_service(db).get_by_id(user_id)

    gmail_service = get_gmail_auth_service(user_id)
    auth_url, error = gmail_service.get_auth_url()

    if error:
        raise HTTPException(status_code=400, detail=error)

    return {"auth_url": auth_url}


@router.post("/gmail-auth-complete")
async def complete_gmail_auth(
    user_id: int, request: GmailAuthCompleteRequest, db: Session = Depends(get_db)
):
    """
    Complete OAuth flow with authorization code.
    The user pastes the code they received after authorizing.
    """
    get_user_service(db).get_by_id(user_id)

    gmail_service = get_gmail_auth_service(user_id)
    success, message = gmail_service.complete_auth(request.auth_code)

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"message": message}


@router.post("/gmail-disconnect")
async def disconnect_gmail(user_id: int, db: Session = Depends(get_db)):
    """
    Disconnect Gmail by removing the token.
    User will need to re-authorize to send emails.
    """
    get_user_service(db).get_by_id(user_id)

    gmail_service = get_gmail_auth_service(user_id)
    success, message = gmail_service.disconnect_gmail()

    if not success:
        raise HTTPException(status_code=400, detail=message)

    return {"message": message}


@router.post("/resume")
async def upload_resume(user_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload resume PDF for a user."""
    get_user_service(db).get_by_id(user_id)

    if not file.filename or not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    gmail_service = get_gmail_auth_service(user_id)
    content = await file.read()
    success, message = gmail_service.save_resume(content, file.filename)

    if not success:
        raise HTTPException(status_code=500, detail=message)

    return {"message": message}
