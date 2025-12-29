import pytest
from fastapi import status
import io
import csv


def test_create_recipient(client):
    """Test creating a new recipient"""
    response = client.post(
        "/recipients/",
        json={
            "email": "newrecipient@example.com",
            "first_name": "Jane",
            "last_name": "Smith",
            "company": "New Company"
        }
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
        json={
            "email": test_recipient.email,
            "first_name": "Different",
            "last_name": "Person"
        }
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
    csv_bytes = csv_file.getvalue().encode('utf-8')
    csv_file_obj = io.BytesIO(csv_bytes)
    
    response = client.post(
        f"/users/{test_user.id}/recipients-csv",
        files={"file": ("test.csv", csv_file_obj, "text/csv")}
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
    from database import User, Recipient, EmailLog, EmailStatus
    from datetime import datetime, timezone
    
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
            sent_at=datetime.now(timezone.utc)
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

