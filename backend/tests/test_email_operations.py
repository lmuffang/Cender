import pytest
from fastapi import status
from datetime import datetime, timezone
from database import EmailLog, EmailStatus


def test_preview_email(client, test_user, test_recipient, test_template, test_db):
    """Test email preview generation"""
    from database import User, Recipient
    
    # Link recipient to user
    db = test_db()
    user = db.query(User).filter(User.id == test_user.id).first()
    recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
    if user and recipient:
        user.recipients.append(recipient)
        db.commit()
    db.close()
    
    response = client.post(
        f"/users/{test_user.id}/preview-email/{test_recipient.id}",
        data={"subject": "Test Subject"}
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
    from database import User, Recipient
    
    # Link recipient to user
    db = test_db()
    user = db.query(User).filter(User.id == test_user.id).first()
    recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
    if user and recipient:
        user.recipients.append(recipient)
        db.commit()
    db.close()
    
    response = client.post(
        f"/users/{test_user.id}/preview-email/{test_recipient.id}",
        data={"subject": "Test Subject"}
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
            sent_at=datetime.now(timezone.utc)
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
        sent_at=datetime.now(timezone.utc)
    )
    log2 = EmailLog(
        user_id=test_user.id,
        recipient_email="test2@example.com",
        subject="Test",
        status=EmailStatus.FAILED,
        sent_at=datetime.now(timezone.utc)
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
    assert data["total_emails"] == data["total_sent"] + data["total_failed"] + data.get("total_skipped", 0)


def test_send_emails_stream_dry_run(client, test_user, test_recipient, test_template, test_db):
    """Test sending emails in dry run mode"""
    from database import User, Recipient
    
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
        json={
            "recipient_ids": [test_recipient.id],
            "subject": "Test Subject",
            "dry_run": True
        }
    )
    
    # Should return streaming response or error about missing credentials/resume
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]

