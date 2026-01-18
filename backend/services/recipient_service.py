"""Recipient service layer."""

from sqlalchemy.orm import Session

from database import Recipient, user_recipients, EmailLog, EmailStatus
from exceptions import RecipientNotFoundError, UserNotFoundError
from services.user_service import UserService
from utils.logger import logger


class RecipientService:
    """Service for recipient operations."""

    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)

    def create(
        self,
        email: str,
        first_name: str | None = None,
        last_name: str | None = None,
        company: str | None = None,
    ) -> Recipient:
        """
        Create a new recipient.

        Args:
            email: Email address
            first_name: First name
            last_name: Last name
            company: Company name

        Returns:
            Created recipient

        Raises:
            ValueError: If recipient with email already exists
        """
        existing = self.db.query(Recipient).filter(Recipient.email == email).first()
        if existing:
            logger.warning(f"Attempt to create recipient with existing email: {email}")
            raise ValueError(f"Recipient with email {email} already exists")

        recipient = Recipient(
            email=email, first_name=first_name, last_name=last_name, company=company
        )
        self.db.add(recipient)
        self.db.commit()
        self.db.refresh(recipient)
        logger.info(f"Created recipient: {recipient.id} ({email})")
        return recipient

    def get_by_id(self, recipient_id: int) -> Recipient:
        """
        Get recipient by ID.

        Args:
            recipient_id: Recipient ID

        Returns:
            Recipient instance

        Raises:
            RecipientNotFoundError: If recipient not found
        """
        recipient = self.db.query(Recipient).filter(Recipient.id == recipient_id).first()
        if not recipient:
            raise RecipientNotFoundError(f"Recipient with id {recipient_id} not found")
        return recipient

    def get_by_user(self, user_id: int, used: bool | None = None) -> list[Recipient]:
        """
        Get recipients for a user, optionally filtered by usage.

        Args:
            user_id: User ID
            used: Filter by usage status (True=used, False=unused, None=all)

        Returns:
            List of recipients
        """
        # Verify user exists
        self.user_service.get_by_id(user_id)

        # Base query: recipients linked to user
        query = (
            self.db.query(Recipient)
            .join(user_recipients)
            .filter(user_recipients.c.user_id == user_id)
        )

        if used is not None:
            # Subquery for sent emails
            sent_subquery = (
                self.db.query(EmailLog.recipient_id)
                .filter(
                    EmailLog.user_id == user_id,
                    EmailLog.status == EmailStatus.SENT,
                    EmailLog.recipient_id.isnot(None),
                )
                .subquery()
            )

            if used:
                query = query.filter(Recipient.id.in_(self.db.query(sent_subquery.c.recipient_id)))
            else:
                query = query.filter(~Recipient.id.in_(self.db.query(sent_subquery.c.recipient_id)))

        return query.all()

    def link_to_user(self, user_id: int, recipient_id: int) -> None:
        """
        Link recipient to user.

        Args:
            user_id: User ID
            recipient_id: Recipient ID
        """
        user = self.user_service.get_by_id(user_id)
        recipient = self.get_by_id(recipient_id)

        if recipient not in user.recipients:
            user.recipients.append(recipient)
            self.db.commit()
            logger.info(f"Linked recipient {recipient_id} to user {user_id}")

    def unlink_all_from_user(self, user_id: int) -> int:
        """
        Unlink all recipients from a user.

        This removes the user-recipient associations but does not delete
        the recipients themselves (they may be linked to other users).

        Args:
            user_id: User ID

        Returns:
            Number of recipients unlinked

        Raises:
            UserNotFoundError: If user not found
        """
        user = self.user_service.get_by_id(user_id)
        count = len(user.recipients)
        user.recipients.clear()
        self.db.commit()
        logger.info(f"Unlinked {count} recipients from user {user_id}")
        return count
