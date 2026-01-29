"""Tests for Gmail authentication endpoints."""

from unittest.mock import MagicMock, patch

from fastapi import status
from services.gmail_auth_service import GmailStatus, UserFilesStatus


class TestGmailStatus:
    """Tests for GET /users/{user_id}/gmail-status endpoint."""

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_get_gmail_status_not_connected(
        self, mock_get_service, client, test_user
    ):
        """Test getting Gmail status when not connected."""
        mock_service = MagicMock()
        mock_service.get_gmail_status.return_value = GmailStatus(
            connected=False,
            has_credentials=False,
            has_token=False,
            email=None,
            error=None,
        )
        mock_get_service.return_value = mock_service

        response = client.get(f"/users/{test_user.id}/gmail-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connected"] is False
        assert data["has_credentials"] is False
        assert data["has_token"] is False
        assert data["email"] is None
        mock_service.get_gmail_status.assert_called_once()

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_get_gmail_status_connected(
        self, mock_get_service, client, test_user
    ):
        """Test getting Gmail status when connected."""
        mock_service = MagicMock()
        mock_service.get_gmail_status.return_value = GmailStatus(
            connected=True,
            has_credentials=True,
            has_token=True,
            email="user@gmail.com",
            error=None,
        )
        mock_get_service.return_value = mock_service

        response = client.get(f"/users/{test_user.id}/gmail-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["connected"] is True
        assert data["has_credentials"] is True
        assert data["has_token"] is True
        assert data["email"] == "user@gmail.com"
        mock_service.get_gmail_status.assert_called_once()

    def test_get_gmail_status_user_not_found(self, client):
        """Test getting Gmail status for non-existent user."""
        response = client.get("/users/99999/gmail-status")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestFilesStatus:
    """Tests for GET /users/{user_id}/files-status endpoint."""

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_get_files_status(
        self, mock_get_service, client, test_user
    ):
        """Test getting files status."""
        mock_service = MagicMock()
        mock_service.get_files_status.return_value = UserFilesStatus(
            has_credentials=True,
            has_resume=False,
            credentials_path="/path/to/credentials.json",
            resume_path="/path/to/resume.pdf",
        )
        mock_get_service.return_value = mock_service

        response = client.get(f"/users/{test_user.id}/files-status")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["has_credentials"] is True
        assert data["has_resume"] is False
        mock_service.get_files_status.assert_called_once()

    def test_get_files_status_user_not_found(self, client):
        """Test getting files status for non-existent user."""
        response = client.get("/users/99999/files-status")

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestGmailAuthUrl:
    """Tests for POST /users/{user_id}/gmail-auth-url endpoint."""

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_get_gmail_auth_url_success(
        self, mock_get_service, client, test_user
    ):
        """Test getting OAuth authorization URL successfully."""
        mock_service = MagicMock()
        mock_service.get_auth_url.return_value = (
            "https://accounts.google.com/o/oauth2/auth?...",
            None,
        )
        mock_get_service.return_value = mock_service

        response = client.post(f"/users/{test_user.id}/gmail-auth-url")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "auth_url" in data
        assert data["auth_url"] == "https://accounts.google.com/o/oauth2/auth?..."
        mock_service.get_auth_url.assert_called_once()

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_get_gmail_auth_url_no_credentials(
        self, mock_get_service, client, test_user
    ):
        """Test getting auth URL when credentials not uploaded."""
        mock_service = MagicMock()
        mock_service.get_auth_url.return_value = (
            None,
            "Credentials file not uploaded. Please upload credentials.json first.",
        )
        mock_get_service.return_value = mock_service

        response = client.post(f"/users/{test_user.id}/gmail-auth-url")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "credentials" in data["detail"].lower()


class TestGmailAuthComplete:
    """Tests for POST /users/{user_id}/gmail-auth-complete endpoint."""

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_complete_gmail_auth_success(
        self, mock_get_service, client, test_user
    ):
        """Test completing OAuth flow successfully."""
        mock_service = MagicMock()
        mock_service.complete_auth.return_value = (True, "Gmail connected successfully!")
        mock_get_service.return_value = mock_service

        response = client.post(
            f"/users/{test_user.id}/gmail-auth-complete",
            json={"auth_code": "4/0ABC123..."},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "Gmail connected successfully!"
        mock_service.complete_auth.assert_called_once_with("4/0ABC123...")

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_complete_gmail_auth_invalid_code(
        self, mock_get_service, client, test_user
    ):
        """Test completing OAuth with invalid authorization code."""
        mock_service = MagicMock()
        mock_service.complete_auth.return_value = (
            False,
            "Authorization failed: invalid_grant",
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            f"/users/{test_user.id}/gmail-auth-complete",
            json={"auth_code": "invalid-code"},
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert "failed" in data["detail"].lower()


class TestGmailDisconnect:
    """Tests for POST /users/{user_id}/gmail-disconnect endpoint."""

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_disconnect_gmail_success(
        self, mock_get_service, client, test_user
    ):
        """Test disconnecting Gmail successfully."""
        mock_service = MagicMock()
        mock_service.disconnect_gmail.return_value = (
            True,
            "Gmail disconnected successfully",
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            f"/users/{test_user.id}/gmail-disconnect"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "disconnected" in data["message"].lower()
        mock_service.disconnect_gmail.assert_called_once()

    @patch("api.routers.gmail.get_gmail_auth_service")
    def test_disconnect_gmail_not_connected(
        self, mock_get_service, client, test_user
    ):
        """Test disconnect when Gmail was not connected (idempotent)."""
        mock_service = MagicMock()
        mock_service.disconnect_gmail.return_value = (
            True,
            "Gmail was not connected",
        )
        mock_get_service.return_value = mock_service

        response = client.post(
            f"/users/{test_user.id}/gmail-disconnect"
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "not connected" in data["message"].lower()
        mock_service.disconnect_gmail.assert_called_once()
