"""Tests for user management endpoints."""

from datetime import datetime, timezone

from database import EmailLog, EmailStatus, Recipient, Template, User
from fastapi import status


def test_create_user(client):
    """Test creating a new user"""
    response = client.post("/users/", json={"username": "newuser", "email": "newuser@example.com"})
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == "newuser"
    assert data["email"] == "newuser@example.com"
    assert "id" in data


def test_create_user_duplicate_email(client):
    """Test creating a user with duplicate email"""
    # Create first user
    client.post("/users/", json={"username": "user1", "email": "duplicate@example.com"})

    # Try to create second user with same email
    response = client.post("/users/", json={"username": "user2", "email": "duplicate@example.com"})
    assert response.status_code == status.HTTP_409_CONFLICT


def test_list_users(client, test_user):
    """Test listing all users"""
    response = client.get("/users/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(user["id"] == test_user.id for user in data)


def test_get_user(client, test_user):
    """Test getting a specific user"""
    response = client.get(f"/users/{test_user.id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == test_user.id
    assert data["username"] == test_user.username
    assert data["email"] == test_user.email


def test_get_user_not_found(client):
    """Test getting a non-existent user"""
    response = client.get("/users/99999")
    assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDeleteUser:
    """Tests for DELETE /users/{user_id} endpoint."""

    def test_delete_user_success(self, client, test_user):
        """Test deleting a user returns 200."""
        response = client.delete(f"/users/{test_user.id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "deleted" in data["message"].lower()
        assert "deleted" in data

        # Verify user no longer exists
        response = client.get(f"/users/{test_user.id}")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_delete_user_cascade_template(self, client, test_user, test_template, test_db):
        """Test that user deletion cascades to template."""
        # Verify template exists
        db = test_db()
        template = db.query(Template).filter(Template.user_id == test_user.id).first()
        assert template is not None
        db.close()

        # Delete user
        response = client.delete(f"/users/{test_user.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"]["template"] is True

        # Verify template is deleted
        db = test_db()
        template = db.query(Template).filter(Template.user_id == test_user.id).first()
        assert template is None
        db.close()

    def test_delete_user_cascade_email_logs(self, client, test_user, test_db):
        """Test that user deletion cascades to email logs."""
        # Create email logs for user
        db = test_db()
        log = EmailLog(
            user_id=test_user.id,
            recipient_email="test@example.com",
            subject="Test",
            status=EmailStatus.SENT,
            sent_at=datetime.now(timezone.utc),
        )
        db.add(log)
        db.commit()
        db.close()

        # Verify log exists
        db = test_db()
        logs = db.query(EmailLog).filter(EmailLog.user_id == test_user.id).all()
        assert len(logs) == 1
        db.close()

        # Delete user
        response = client.delete(f"/users/{test_user.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"]["email_logs"] == 1

        # Verify logs are deleted
        db = test_db()
        logs = db.query(EmailLog).filter(EmailLog.user_id == test_user.id).all()
        assert len(logs) == 0
        db.close()

    def test_delete_user_unlinks_recipients(self, client, test_user, test_recipient, test_db):
        """Test that user deletion unlinks recipients but preserves them."""
        # Link recipient to user
        db = test_db()
        user = db.query(User).filter(User.id == test_user.id).first()
        recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
        user.recipients.append(recipient)
        db.commit()
        db.close()

        # Verify link exists
        db = test_db()
        user = db.query(User).filter(User.id == test_user.id).first()
        assert len(user.recipients) == 1
        db.close()

        # Delete user
        response = client.delete(f"/users/{test_user.id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["deleted"]["recipient_links"] == 1

        # Verify recipient still exists
        db = test_db()
        recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
        assert recipient is not None
        assert recipient.email == test_recipient.email
        db.close()

    def test_delete_user_not_found(self, client):
        """Test deleting a non-existent user returns 404."""
        response = client.delete("/users/99999")

        assert response.status_code == status.HTTP_404_NOT_FOUND
