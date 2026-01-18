"""Tests for recipient management endpoints."""

import csv
import io
from datetime import datetime, timezone

from fastapi import status

from database import EmailLog, EmailStatus, Recipient, User


def test_create_recipient(client):
    """Test creating a new recipient"""
    response = client.post(
        "/recipients/",
        json={
            "email": "newrecipient@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "company": "New Company",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "newrecipient@example.com"
    assert data["first_name"] == "Jane"
    assert data["last_name"] == "Smith"
    assert data["company"] == "New Company"
    assert "id" in data


def test_create_recipient_duplicate_email(client, test_recipient):
    """Test creating recipient with duplicate email"""
    response = client.post(
        "/recipients/",
        json={"email": test_recipient.email, "first_name": "Different", "last_name": "Person"},
    )
    assert response.status_code == status.HTTP_409_CONFLICT


def test_get_recipient(client, test_recipient):
    """Test getting a specific recipient"""
    response = client.get(f"/recipients/{test_recipient.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_recipient.id
    assert data["email"] == test_recipient.email


def test_get_recipient_not_found(client):
    """Test getting non-existent recipient"""
    response = client.get("/recipients/99999")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_list_recipients_empty(client, test_user):
    """Test listing recipients for user with no recipients"""
    response = client.get(f"/users/{test_user.id}/recipients")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_import_recipients_csv(client, test_user):
    """Test importing recipients from CSV"""
    # Create CSV content
    csv_data = [
        ["Email", "First Name", "Last Name", "Company"],
        ["test1@example.com", "John", "Doe", "Company 1"],
        ["test2@example.com", "Jane", "Smith", "2342"],
        ["test3@example.com", "Bob", "Johnson", ""],
    ]

    # Create file-like object
    csv_file = io.StringIO()
    writer = csv.writer(csv_file)
    writer.writerows(csv_data)
    csv_file.seek(0)

    # Convert to bytes
    csv_bytes = csv_file.getvalue().encode("utf-8")
    csv_file_obj = io.BytesIO(csv_bytes)

    response = client.post(
        f"/users/{test_user.id}/recipients-csv",
        files={"file": ("test.csv", csv_file_obj, "text/csv")},
    )

    assert response.status_code == status.HTTP_200_OK, response.json()
    data = response.json()
    assert data["created"] == 3
    assert data["linked"] == 3

    # Verify recipients are linked to user
    response = client.get(f"/users/{test_user.id}/recipients")
    assert response.status_code == status.HTTP_200_OK
    recipients = response.json()
    assert len(recipients) == 3


def test_list_recipients_filter_used(client, test_user, test_recipient, test_db):
    """Test filtering recipients by usage status"""
    # Link recipient to user
    db = test_db()
    user = db.query(User).filter(User.id == test_user.id).first()
    recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
    if user and recipient:
        user.recipients.append(recipient)
        db.commit()

        # Create email log for this recipient
        email_log = EmailLog(
            user_id=test_user.id,
            recipient_id=test_recipient.id,
            recipient_email=test_recipient.email,
            subject="Test",
            status=EmailStatus.SENT,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(email_log)
        db.commit()
    db.close()

    # Test filtering for used recipients
    response = client.get(f"/users/{test_user.id}/recipients?used=true")
    assert response.status_code == status.HTTP_200_OK
    recipients = response.json()
    assert len(recipients) >= 1

    # Test filtering for unused recipients
    response = client.get(f"/users/{test_user.id}/recipients?used=false")
    assert response.status_code == status.HTTP_200_OK
    recipients = response.json()
    # Should not include the used recipient
    assert not any(r["id"] == test_recipient.id for r in recipients)


class TestDeleteUserRecipients:
    """Tests for DELETE /users/{user_id}/recipients endpoint."""

    def test_delete_all_user_recipients(self, client, test_user, test_db):
        """Test deleting all recipients from a user."""
        # Create and link recipients to user
        db = test_db()
        user = db.query(User).filter(User.id == test_user.id).first()
        for i in range(3):
            recipient = Recipient(
                email=f"recipient{i}@example.com",
                first_name=f"Name{i}",
            )
            db.add(recipient)
            db.flush()
            user.recipients.append(recipient)
        db.commit()
        db.close()

        # Verify recipients are linked
        response = client.get(f"/users/{test_user.id}/recipients")
        assert len(response.json()) == 3

        # Delete all recipients from user
        response = client.delete(f"/users/{test_user.id}/recipients")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 3
        assert "removed" in data["message"].lower()

        # Verify no recipients linked to user
        response = client.get(f"/users/{test_user.id}/recipients")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()) == 0

    def test_delete_user_recipients_preserves_recipients(self, client, test_user, test_db):
        """Test that unlinking recipients preserves the recipient records."""
        # Create and link a recipient
        db = test_db()
        user = db.query(User).filter(User.id == test_user.id).first()
        recipient = Recipient(
            email="preserved@example.com",
            first_name="Preserved",
            last_name="User",
        )
        db.add(recipient)
        db.flush()
        recipient_id = recipient.id
        user.recipients.append(recipient)
        db.commit()
        db.close()

        # Delete recipients from user
        response = client.delete(f"/users/{test_user.id}/recipients")
        assert response.status_code == status.HTTP_200_OK

        # Verify recipient still exists in database
        response = client.get(f"/recipients/{recipient_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["email"] == "preserved@example.com"
        assert data["first_name"] == "Preserved"

    def test_delete_user_recipients_user_not_found(self, client):
        """Test deleting recipients for non-existent user returns 404."""
        response = client.delete("/users/99999/recipients")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestCSVImport:
    """Additional tests for CSV import."""

    def test_import_csv_empty_emails_skipped(self, client, test_user):
        """Test that rows with empty or NaN emails are skipped during CSV import."""
        # Create CSV with some empty emails (truly empty, not whitespace)
        csv_content = """Email,First Name,Last Name,Company
valid@example.com,Valid,User,Company1
,Empty,Email,Company2
another@example.com,Another,User,Company3"""

        csv_bytes = csv_content.encode("utf-8")

        response = client.post(
            f"/users/{test_user.id}/recipients-csv",
            files={"file": ("test.csv", csv_bytes, "text/csv")},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        # Only 2 valid emails should be processed (empty string is skipped)
        assert data["created"] == 2
        assert data["linked"] == 2

        # Verify only valid recipients are linked
        response = client.get(f"/users/{test_user.id}/recipients")
        recipients = response.json()
        assert len(recipients) == 2
        emails = [r["email"] for r in recipients]
        assert "valid@example.com" in emails
        assert "another@example.com" in emails


class TestPreviewEmail:
    """Additional tests for email preview."""

    def test_preview_email_recipient_not_linked(self, client, test_user, test_recipient, test_template):
        """Test that preview fails for unlinked recipient with 403."""
        # Recipient exists but is not linked to user
        response = client.post(
            f"/users/{test_user.id}/preview-email/{test_recipient.id}",
            data={"subject": "Test Subject"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        data = response.json()
        assert "not linked" in data["detail"].lower()
