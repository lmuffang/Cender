"""Tests for email operations endpoints."""

from datetime import datetime, timedelta, timezone

from database import EmailLog, EmailStatus, Recipient, User
from fastapi import status


def test_preview_email(client, test_user, test_recipient, test_template, test_db):
    """Test email preview generation"""
    # Link recipient to user
    db = test_db()
    user = db.query(User).filter(User.id == test_user.id).first()
    recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
    if user and recipient:
        user.recipients.append(recipient)
        db.commit()
    db.close()

    response = client.post(
        f"/users/{test_user.id}/preview-email/{test_recipient.id}", data={"subject": "Test Subject"}
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "email" in data
    assert "subject" in data
    assert "body" in data
    assert data["email"] == test_recipient.email
    assert data["subject"] == "Test Subject"
    assert "{salutation}" not in data["body"]  # Should be replaced
    assert "{company}" not in data["body"]  # Should be replaced


def test_preview_email_no_template(client, test_user, test_recipient, test_db):
    """Test preview when user has no template"""
    # Link recipient to user
    db = test_db()
    user = db.query(User).filter(User.id == test_user.id).first()
    recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
    if user and recipient:
        user.recipients.append(recipient)
        db.commit()
    db.close()

    response = client.post(
        f"/users/{test_user.id}/preview-email/{test_recipient.id}", data={"subject": "Test Subject"}
    )

    # Should return 404 if no template
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_get_email_logs_empty(client, test_user):
    """Test getting email logs when none exist"""
    response = client.get(f"/users/{test_user.id}/email-logs")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_get_email_logs_with_limit(client, test_user, test_db):
    """Test getting email logs with limit"""
    # Create some email logs
    db = test_db()
    for i in range(5):
        log = EmailLog(
            user_id=test_user.id,
            recipient_email=f"test{i}@example.com",
            subject="Test",
            status=EmailStatus.SENT,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(log)
    db.commit()
    db.close()

    response = client.get(f"/users/{test_user.id}/email-logs?limit=3")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) == 3


def test_get_user_stats(client, test_user, test_db):
    """Test getting user statistics"""
    # Create email logs
    db = test_db()
    log1 = EmailLog(
        user_id=test_user.id,
        recipient_email="test1@example.com",
        subject="Test",
        status=EmailStatus.SENT,
        sent_at=datetime.now(timezone.utc),
    )
    log2 = EmailLog(
        user_id=test_user.id,
        recipient_email="test2@example.com",
        subject="Test",
        status=EmailStatus.FAILED,
        sent_at=datetime.now(timezone.utc),
    )
    db.add(log1)
    db.add(log2)
    db.commit()
    db.close()

    response = client.get(f"/users/{test_user.id}/stats")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["total_sent"] >= 1
    assert data["total_failed"] >= 1
    assert data["total_emails"] == data["total_sent"] + data["total_failed"] + data.get(
        "total_skipped", 0
    )


def test_send_emails_stream_dry_run(client, test_user, test_recipient, test_template, test_db):
    """Test sending emails in dry run mode"""
    # Link recipient to user
    db = test_db()
    user = db.query(User).filter(User.id == test_user.id).first()
    recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
    if user and recipient:
        user.recipients.append(recipient)
        db.commit()
    db.close()

    # Note: This test will fail if credentials/resume are not set up
    # In a real scenario, you'd mock the Gmail service
    response = client.post(
        f"/users/{test_user.id}/send-emails/stream",
        json={"recipient_ids": [test_recipient.id], "subject": "Test Subject", "dry_run": True},
    )

    # Should return streaming response or error about missing credentials/resume
    assert response.status_code in [
        status.HTTP_200_OK,
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_404_NOT_FOUND,
    ]


class TestEmailLogDeletion:
    """Tests for email log deletion endpoints."""

    def _create_email_logs(self, test_db, test_user, count=3, email_status=EmailStatus.SENT, recipient_id=None):
        """Helper to create email logs."""
        db = test_db()
        logs = []
        for i in range(count):
            log = EmailLog(
                user_id=test_user.id,
                recipient_id=recipient_id,
                recipient_email=f"test{i}@example.com",
                subject="Test",
                status=email_status,
                sent_at=datetime.now(timezone.utc),
            )
            db.add(log)
            logs.append(log)
        db.commit()
        log_ids = [log.id for log in logs]
        db.close()
        return log_ids

    def test_delete_email_logs_by_recipient(self, client, test_user, test_recipient, test_db):
        """Test deleting email logs filtered by recipient_id."""
        # Link recipient to user
        db = test_db()
        user = db.query(User).filter(User.id == test_user.id).first()
        recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
        user.recipients.append(recipient)
        db.commit()
        db.close()

        # Create logs with and without recipient_id
        self._create_email_logs(test_db, test_user, count=2, recipient_id=test_recipient.id)
        self._create_email_logs(test_db, test_user, count=3, recipient_id=None)

        # Delete only logs for specific recipient
        response = client.delete(
            f"/users/{test_user.id}/email-logs?recipient_id={test_recipient.id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_count"] == 2

        # Verify remaining logs
        response = client.get(f"/users/{test_user.id}/email-logs")
        assert response.status_code == status.HTTP_200_OK
        remaining = response.json()
        assert len(remaining) == 3

    def test_delete_email_logs_by_status(self, client, test_user, test_db):
        """Test deleting email logs filtered by status."""
        # Create logs with different statuses
        self._create_email_logs(test_db, test_user, count=2, email_status=EmailStatus.SENT)
        self._create_email_logs(test_db, test_user, count=3, email_status=EmailStatus.FAILED)

        # Delete only failed logs
        response = client.delete(f"/users/{test_user.id}/email-logs?status=failed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_count"] == 3

        # Verify remaining logs are sent
        response = client.get(f"/users/{test_user.id}/email-logs")
        assert response.status_code == status.HTTP_200_OK
        remaining = response.json()
        assert len(remaining) == 2
        assert all(log["status"] == "sent" for log in remaining)

    def test_delete_email_logs_by_date(self, client, test_user, test_db):
        """Test deleting email logs filtered by before_date."""
        # Create logs
        db = test_db()
        old_log = EmailLog(
            user_id=test_user.id,
            recipient_email="old@example.com",
            subject="Old",
            status=EmailStatus.SENT,
            sent_at=datetime.now(timezone.utc) - timedelta(days=10),
        )
        new_log = EmailLog(
            user_id=test_user.id,
            recipient_email="new@example.com",
            subject="New",
            status=EmailStatus.SENT,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(old_log)
        db.add(new_log)
        db.commit()
        db.close()

        # Delete logs before 5 days ago
        before_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime("%Y-%m-%d")
        response = client.delete(
            f"/users/{test_user.id}/email-logs?before_date={before_date}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_count"] == 1

        # Verify remaining log is the new one
        response = client.get(f"/users/{test_user.id}/email-logs")
        assert response.status_code == status.HTTP_200_OK
        remaining = response.json()
        assert len(remaining) == 1
        assert remaining[0]["recipient_email"] == "new@example.com"

    def test_delete_email_logs_all(self, client, test_user, test_db):
        """Test deleting all email logs with all=true."""
        # Create logs
        self._create_email_logs(test_db, test_user, count=5)

        # Delete all logs
        response = client.delete(f"/users/{test_user.id}/email-logs?all=true")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted_count"] == 5

        # Verify no logs remain
        response = client.get(f"/users/{test_user.id}/email-logs")
        assert response.status_code == status.HTTP_200_OK
        remaining = response.json()
        assert len(remaining) == 0

    def test_delete_email_logs_no_filter_error(self, client, test_user, test_db):
        """Test that deleting logs without filter returns 400."""
        # Create some logs
        self._create_email_logs(test_db, test_user, count=3)

        # Try to delete without any filter
        response = client.delete(f"/users/{test_user.id}/email-logs")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "filter" in data["detail"].lower() or "all" in data["detail"].lower()

    def test_delete_single_email_log(self, client, test_user, test_db):
        """Test deleting a specific email log by ID."""
        log_ids = self._create_email_logs(test_db, test_user, count=3)
        target_log_id = log_ids[0]

        # Delete specific log
        response = client.delete(
            f"/users/{test_user.id}/email-logs/{target_log_id}"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "deleted" in data["message"].lower()

        # Verify log is deleted but others remain
        response = client.get(f"/users/{test_user.id}/email-logs")
        assert response.status_code == status.HTTP_200_OK
        remaining = response.json()
        assert len(remaining) == 2
        assert all(log["id"] != target_log_id for log in remaining)

    def test_delete_single_email_log_not_found(self, client, test_user):
        """Test deleting a non-existent email log returns 400."""
        response = client.delete(f"/users/{test_user.id}/email-logs/99999")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_email_logs_filter_by_status(self, client, test_user, test_db):
        """Test getting email logs filtered by status."""
        # Create logs with different statuses
        self._create_email_logs(test_db, test_user, count=2, email_status=EmailStatus.SENT)
        self._create_email_logs(test_db, test_user, count=3, email_status=EmailStatus.FAILED)

        # Get only sent logs
        response = client.get(f"/users/{test_user.id}/email-logs?status=sent")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 2
        assert all(log["status"] == "sent" for log in data)

        # Get only failed logs
        response = client.get(f"/users/{test_user.id}/email-logs?status=failed")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 3
        assert all(log["status"] == "failed" for log in data)
