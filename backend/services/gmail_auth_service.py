"""Gmail authentication service layer."""

import os
from dataclasses import dataclass

from config import settings
from gmail_service import (
    get_authorization_url,
    complete_authorization,
    check_gmail_connection,
)
from utils.logger import logger


@dataclass
class GmailStatus:
    """Gmail connection status."""
    connected: bool
    has_credentials: bool
    has_token: bool
    email: str | None
    error: str | None


@dataclass
class UserFilesStatus:
    """Status of user's uploaded files."""
    has_credentials: bool
    has_resume: bool
    credentials_path: str
    resume_path: str


class GmailAuthService:
    """Service for Gmail authentication operations."""

    def __init__(self, user_id: int):
        self.user_id = user_id
        self.credentials_path = settings.get_credentials_path(user_id)
        self.token_path = settings.get_token_path(user_id)
        self.resume_path = settings.get_resume_path(user_id)

    def get_files_status(self) -> UserFilesStatus:
        """Check if user has uploaded credentials and resume."""
        return UserFilesStatus(
            has_credentials=os.path.exists(self.credentials_path),
            has_resume=os.path.exists(self.resume_path),
            credentials_path=self.credentials_path,
            resume_path=self.resume_path,
        )

    def get_gmail_status(self) -> GmailStatus:
        """Check Gmail connection status."""
        result = check_gmail_connection(self.credentials_path, self.token_path)
        return GmailStatus(
            connected=result["connected"],
            has_credentials=result["has_credentials"],
            has_token=result["has_token"],
            email=result["email"],
            error=result["error"],
        )

    def get_auth_url(self) -> tuple[str | None, str | None]:
        """
        Get OAuth authorization URL.

        Returns:
            Tuple of (auth_url, error_message)
        """
        if not os.path.exists(self.credentials_path):
            return None, "Credentials file not uploaded. Please upload credentials.json first."

        try:
            auth_url, _ = get_authorization_url(
                self.credentials_path,
                redirect_uri="http://localhost"
            )
            logger.info(f"Generated auth URL for user {self.user_id}")
            return auth_url, None
        except Exception as e:
            logger.error(f"Failed to generate auth URL for user {self.user_id}: {e}")
            return None, f"Failed to generate auth URL: {str(e)}"

    def complete_auth(self, auth_code: str) -> tuple[bool, str]:
        """
        Complete OAuth flow with authorization code.

        Args:
            auth_code: Authorization code from OAuth redirect

        Returns:
            Tuple of (success, message)
        """
        if not os.path.exists(self.credentials_path):
            return False, "Credentials file not uploaded. Please upload credentials.json first."

        try:
            complete_authorization(
                credentials_path=self.credentials_path,
                auth_code=auth_code.strip(),
                token_path=self.token_path,
                redirect_uri="http://localhost"
            )
            logger.info(f"Gmail authorization completed for user {self.user_id}")
            return True, "Gmail connected successfully!"
        except Exception as e:
            logger.error(f"Gmail authorization failed for user {self.user_id}: {e}")
            return False, f"Authorization failed: {str(e)}"

    def save_credentials(self, content: bytes) -> tuple[bool, str]:
        """
        Save credentials file.

        Args:
            content: File content bytes

        Returns:
            Tuple of (success, message)
        """
        try:
            os.makedirs(os.path.dirname(self.credentials_path), exist_ok=True)
            with open(self.credentials_path, "wb") as f:
                f.write(content)
            logger.info(f"Credentials saved for user {self.user_id}")
            return True, "Credentials uploaded successfully"
        except Exception as e:
            logger.error(f"Failed to save credentials for user {self.user_id}: {e}")
            return False, f"Failed to save credentials: {str(e)}"

    def save_resume(self, content: bytes) -> tuple[bool, str]:
        """
        Save resume file.

        Args:
            content: File content bytes

        Returns:
            Tuple of (success, message)
        """
        try:
            os.makedirs(os.path.dirname(self.resume_path), exist_ok=True)
            with open(self.resume_path, "wb") as f:
                f.write(content)
            logger.info(f"Resume saved for user {self.user_id}")
            return True, "Resume uploaded successfully"
        except Exception as e:
            logger.error(f"Failed to save resume for user {self.user_id}: {e}")
            return False, f"Failed to save resume: {str(e)}"
