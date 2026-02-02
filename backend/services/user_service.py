"""User service layer."""

import os
import shutil

from config import settings
from database import User
from exceptions import UserNotFoundError
from sqlalchemy.orm import Session
from utils.logger import logger


class UserService:
    """Service for user operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, username: str, email: str) -> User:
        """
        Create a new user.

        Args:
            username: Username
            email: Email address

        Returns:
            Created user

        Raises:
            ValueError: If user with email already exists
        """
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            logger.warning(f"Attempt to create user with existing email: {email}")
            raise ValueError(f"User with email {email} already exists")

        user = User(username=username, email=email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Created user: {user.id} ({username})")
        return user

    def get_by_id(self, user_id: int) -> User:
        """
        Get user by ID.

        Args:
            user_id: User ID

        Returns:
            User instance

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found")
        return user

    def get_all(self) -> list[User]:
        """
        Get all users.

        Returns:
            List of all users
        """
        return self.db.query(User).all()

    def get_by_email(self, email: str) -> User | None:
        """
        Get user by email.

        Args:
            email: Email address

        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.email == email).first()

    def delete(self, user_id: int) -> dict:
        """
        Delete a user and all associated data.

        This will delete:
        - User's template (CASCADE)
        - User's recipient links (CASCADE, recipients themselves are kept)
        - User's email logs (CASCADE)
        - User's files (credentials, token, resume)

        Args:
            user_id: User ID

        Returns:
            Dict with deletion summary

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.get_by_id(user_id)
        username = user.username

        # Count related data before deletion
        email_logs_count = len(user.emails) if user.emails else 0
        has_template = user.template is not None
        recipients_count = len(user.recipients) if user.recipients else 0

        # Delete user files
        files_deleted = []
        files_to_delete = [
            settings.get_credentials_path(user_id),
            settings.get_token_path(user_id),
            settings.get_resume_path(user_id),
        ]

        for file_path in files_to_delete:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    files_deleted.append(os.path.basename(file_path))
                    logger.info(f"Deleted file: {file_path}")
                except OSError as e:
                    logger.error(f"Failed to delete file {file_path}: {e}")

        # Also delete user data directory if it exists
        user_data_dir = settings.get_user_data_dir(user_id)
        if os.path.exists(user_data_dir):
            try:
                shutil.rmtree(user_data_dir)
                files_deleted.append(f"user_{user_id}/")
                logger.info(f"Deleted user data directory: {user_data_dir}")
            except OSError as e:
                logger.error(f"Failed to delete user data directory {user_data_dir}: {e}")

        # Delete user (cascades to template, email_logs, user_recipients)
        self.db.delete(user)
        self.db.commit()

        logger.info(f"Deleted user {user_id} ({username}) and all associated data")

        return {
            "message": f"User '{username}' deleted successfully",
            "deleted": {
                "email_logs": email_logs_count,
                "template": has_template,
                "recipient_links": recipients_count,
                "files": files_deleted,
            },
        }
