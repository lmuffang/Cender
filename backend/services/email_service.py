"""Email service layer."""

import datetime
import json
import os
import time

from config import settings
from database import EmailLog, EmailStatus, Recipient
from exceptions import InvalidCredentialsError, TemplateNotFoundError, UserNotFoundError
from gmail_service import authenticate_gmail, create_message, send_email
from sqlalchemy.orm import Session
from utils.gender_detector import guess_salutation
from utils.logger import logger

from services.recipient_service import RecipientService
from services.template_service import TemplateService
from services.user_service import UserService


class EmailService:
    """Service for email operations."""

    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)
        self.template_service = TemplateService(db)
        self.recipient_service = RecipientService(db)

    def send_emails_stream(
        self,
        user_id: int,
        recipient_ids: list[int],
        subject: str,
        dry_run: bool = False,
    ):
        """
        Stream email sending process.

        Args:
            user_id: User ID
            recipient_ids: List of recipient IDs
            subject: Email subject
            dry_run: If True, don't actually send emails, pause for 0.1sec

        Yields:
            JSON strings with status updates
        """
        # Verify user exists
        user = self.user_service.get_by_id(user_id)

        # Check credentials and resume
        credentials_path = settings.get_credentials_path(user_id)
        resume_path = settings.get_resume_path(user_id)

        if not os.path.exists(credentials_path):
            logger.error(f"Gmail credentials not found for user {user_id}")
            yield json.dumps({"error": "Gmail credentials not uploaded"}) + "\n"
            return

        if not resume_path:
            logger.error(f"Resume not found for user {user_id}")
            yield json.dumps({"error": "Resume not uploaded"}) + "\n"
            return

        # Get template
        template_data = self.template_service.get_or_default(user_id)
        template_content = template_data["content"]

        # Validate recipients belong to user
        user_recipient_ids = {r.id for r in user.recipients}
        invalid_ids = set(recipient_ids) - user_recipient_ids
        if invalid_ids:
            logger.warning(f"User {user_id} attempted to send to recipients {list(invalid_ids)} not linked to them")
            yield json.dumps({"error": f"Recipients {list(invalid_ids)} not linked to this user"}) + "\n"
            return

        # Get recipients
        recipients = self.db.query(Recipient).filter(Recipient.id.in_(recipient_ids)).all()
        if not recipients:
            yield json.dumps({"error": "No valid recipients found"}) + "\n"
            return

        # Get already sent emails
        sent_recipient_ids = {
            log.recipient_id
            for log in self.db.query(EmailLog)
            .filter(
                EmailLog.user_id == user_id,
                EmailLog.status == EmailStatus.SENT,
                EmailLog.recipient_id.isnot(None),
            )
            .all()
        }
        sent_emails = {
            log.recipient_email
            for log in self.db.query(EmailLog)
            .filter(EmailLog.user_id == user_id, EmailLog.status == EmailStatus.SENT)
            .all()
        }

        # Authenticate Gmail service
        service = None
        if not dry_run:
            token_path = settings.get_token_path(user_id)
            try:
                service = authenticate_gmail(credentials_path, token_path)
                logger.info(f"Authenticated Gmail service for user {user_id}")
            except Exception as e:
                logger.error(f"Failed to authenticate Gmail for user {user_id}: {e}")
                yield json.dumps({"error": f"Gmail authentication failed: {str(e)}"}) + "\n"
                return

        # Send emails
        for recipient in recipients:
            email = recipient.email
            recipient_id = recipient.id

            # Check if already sent
            if recipient_id in sent_recipient_ids or email in sent_emails:
                yield json.dumps(
                    {
                        "recipient_id": recipient_id,
                        "email": email,
                        "status": EmailStatus.SKIPPED,
                        "message": "Already sent",
                    }
                ) + "\n"
                continue

            try:
                # Generate salutation
                first_name = recipient.first_name or ""
                last_name = recipient.last_name or ""
                salutation_text = guess_salutation(first_name)
                if last_name:
                    salutation = f"{salutation_text} {last_name}".strip()
                else:
                    salutation = salutation_text

                company = recipient.company or ""

                # Create message
                msg, body = create_message(
                    email,
                    salutation,
                    company,
                    template_content,
                    resume_path,
                    subject,
                )

                if dry_run:
                    logger.debug(f"Dry run: Preview email for {email}")
                    time.sleep(0.1)  # to simulate sent
                    yield json.dumps(
                        {
                            "recipient_id": recipient_id,
                            "email": email,
                            "status": "dry_run",
                            "preview": body,
                        }
                    ) + "\n"
                else:
                    # Send email
                    send_email(service, msg, email)
                    logger.info(f"Sent email to {email} for user {user_id}")

                    # Log success
                    log = EmailLog(
                        user_id=user_id,
                        recipient_id=recipient_id,
                        recipient_email=email,
                        subject=subject,
                        status=EmailStatus.SENT,
                        sent_at=datetime.datetime.now(datetime.timezone.utc),
                    )
                    self.db.add(log)
                    self.db.commit()

                    yield json.dumps(
                        {
                            "recipient_id": recipient_id,
                            "email": email,
                            "status": "sent",
                            "message": "Email sent",
                        }
                    ) + "\n"

            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to send email to {email}: {error_msg}")

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
                    self.db.add(log)
                    self.db.commit()

                yield json.dumps(
                    {
                        "recipient_id": recipient_id,
                        "email": email,
                        "status": "failed",
                        "message": error_msg,
                    }
                ) + "\n"

    def get_logs(
        self, user_id: int, limit: int = 100, status: EmailStatus | None = None
    ) -> list[EmailLog]:
        """
        Get email logs for a user.

        Args:
            user_id: User ID
            limit: Maximum number of logs to return
            status: Filter by status

        Returns:
            List of email logs
        """
        self.user_service.get_by_id(user_id)

        query = self.db.query(EmailLog).filter(EmailLog.user_id == user_id)

        if status:
            query = query.filter(EmailLog.status == status)

        return query.order_by(EmailLog.sent_at.desc()).limit(limit).all()

    def get_stats(self, user_id: int) -> dict:
        """
        Get email statistics for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary with statistics
        """
        self.user_service.get_by_id(user_id)

        total_sent = (
            self.db.query(EmailLog)
            .filter(EmailLog.user_id == user_id, EmailLog.status == EmailStatus.SENT)
            .count()
        )

        total_failed = (
            self.db.query(EmailLog)
            .filter(EmailLog.user_id == user_id, EmailLog.status == EmailStatus.FAILED)
            .count()
        )

        total_skipped = (
            self.db.query(EmailLog)
            .filter(EmailLog.user_id == user_id, EmailLog.status == EmailStatus.SKIPPED)
            .count()
        )

        return {
            "total_sent": total_sent,
            "total_failed": total_failed,
            "total_skipped": total_skipped,
            "total_emails": total_sent + total_failed + total_skipped,
        }

    def delete_logs(
        self,
        user_id: int,
        recipient_id: int | None = None,
        status: EmailStatus | None = None,
        before_date: str | None = None,
        all_logs: bool = False,
    ) -> dict:
        """
        Delete email logs for a user.

        Args:
            user_id: User ID
            recipient_id: Filter by recipient ID
            status: Filter by status
            before_date: Filter by date (YYYY-MM-DD)
            all_logs: Delete all logs

        Returns:
            Dictionary with deletion results
        """
        self.user_service.get_by_id(user_id)

        if not all_logs and not recipient_id and not status and not before_date:
            raise ValueError("Must specify at least one filter or set all_logs=True")

        query = self.db.query(EmailLog).filter(EmailLog.user_id == user_id)

        if recipient_id:
            query = query.filter(EmailLog.recipient_id == recipient_id)

        if status:
            query = query.filter(EmailLog.status == status)

        if before_date:
            try:
                date_obj = datetime.datetime.strptime(before_date, "%Y-%m-%d").replace(
                    tzinfo=datetime.timezone.utc
                )
                query = query.filter(EmailLog.sent_at < date_obj)
            except ValueError:
                raise ValueError("Invalid date format. Use YYYY-MM-DD")

        logs_to_delete = query.all()
        count = len(logs_to_delete)

        for log in logs_to_delete:
            self.db.delete(log)

        self.db.commit()
        logger.info(f"Deleted {count} email log(s) for user {user_id}")

        return {"message": f"Deleted {count} email log(s)", "deleted_count": count}

    def delete_log(self, user_id: int, log_id: int) -> None:
        """
        Delete a specific email log.

        Args:
            user_id: User ID
            log_id: Log ID
        """
        self.user_service.get_by_id(user_id)

        log = (
            self.db.query(EmailLog)
            .filter(EmailLog.id == log_id, EmailLog.user_id == user_id)
            .first()
        )

        if not log:
            raise ValueError(f"Email log {log_id} not found for user {user_id}")

        self.db.delete(log)
        self.db.commit()
        logger.info(f"Deleted email log {log_id} for user {user_id}")
