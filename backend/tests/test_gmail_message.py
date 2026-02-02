"""Tests for Gmail message creation and MIME encoding."""

import base64
import email
import os
import tempfile

from email import policy
from unittest.mock import MagicMock, patch

import pytest

from gmail_service import create_message, send_email


@pytest.fixture
def temp_resume():
    """Create a temporary PDF file for testing."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        # Write minimal PDF content
        f.write(b"%PDF-1.4 minimal test content")
        temp_path = f.name
    yield temp_path
    os.unlink(temp_path)


class TestCreateMessage:
    """Tests for the create_message function."""

    def test_preserves_intentional_newlines(self, temp_resume):
        """Test that intentional newlines in template are preserved."""
        template = "Bonjour {salutation},\n\nParagraph 1.\n\nParagraph 2.\n\nCordialement"

        raw_message, body = create_message(
            to_email="test@example.com",
            salutation="Monsieur Dupont",
            company="TestCorp",
            template=template,
            resume_path=temp_resume,
            subject="Test Subject",
        )

        # Check the body returned directly
        assert "\n\n" in body
        assert body.count("\n") == 6  # 6 newlines in template (2 + 2 + 2)

        # Decode the raw message and check the body
        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        msg = email.message_from_bytes(decoded, policy=policy.default)

        # Get the text part
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                email_body = part.get_content()
                # Should have the same paragraph structure
                assert "Paragraph 1." in email_body
                assert "Paragraph 2." in email_body
                break

    def test_long_lines_not_wrapped_incorrectly(self, temp_resume):
        """Test that long lines don't get unexpected line breaks in the middle of words."""
        # Create a template with a long line (>76 chars)
        long_line = "Je suis particulièrement intéressé par {company} afin d'y mettre en œuvre mes compétences en métrologie et instrumentation."
        template = f"Bonjour {{salutation}},\n\n{long_line}\n\nCordialement"

        raw_message, body = create_message(
            to_email="test@example.com",
            salutation="Monsieur Test",
            company="SuperLongCompanyName",
            template=template,
            resume_path=temp_resume,
            subject="Test Subject",
        )

        # The body string should have the long line intact
        assert "SuperLongCompanyName" in body
        # Should not have newlines in the middle of the sentence (except the intentional ones)
        lines = body.split("\n")
        # Find the line with the long sentence
        long_sentence_line = [l for l in lines if "particulièrement" in l]
        assert len(long_sentence_line) == 1  # Should be exactly one line containing this

        # Decode and verify in the actual email
        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        msg = email.message_from_bytes(decoded, policy=policy.default)

        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                email_body = part.get_content()
                # The word should not be split across lines
                assert "instrumenta\ntion" not in email_body
                assert "mé\ntrologie" not in email_body
                break

    def test_company_name_placeholder(self, temp_resume):
        """Test that both {company} and {company_name} placeholders work."""
        template_with_company = "Working at {company}."
        template_with_company_name = "Working at {company_name}."

        _, body1 = create_message(
            to_email="test@example.com",
            salutation="Mr Test",
            company="ACME Inc",
            template=template_with_company,
            resume_path=temp_resume,
            subject="Test",
        )

        _, body2 = create_message(
            to_email="test@example.com",
            salutation="Mr Test",
            company="ACME Inc",
            template=template_with_company_name,
            resume_path=temp_resume,
            subject="Test",
        )

        assert body1 == "Working at ACME Inc."
        assert body2 == "Working at ACME Inc."

    def test_subject_in_message(self, temp_resume):
        """Test that subject is correctly set in the message."""
        raw_message, _ = create_message(
            to_email="test@example.com",
            salutation="Test",
            company="Test",
            template="Hello {salutation}",
            resume_path=temp_resume,
            subject="Important Subject Line",
        )

        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        msg = email.message_from_bytes(decoded, policy=policy.default)

        assert msg["Subject"] == "Important Subject Line"

    def test_recipient_in_message(self, temp_resume):
        """Test that recipient email is correctly set."""
        raw_message, _ = create_message(
            to_email="recipient@example.com",
            salutation="Test",
            company="Test",
            template="Hello",
            resume_path=temp_resume,
            subject="Test",
        )

        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        msg = email.message_from_bytes(decoded, policy=policy.default)

        assert msg["To"] == "recipient@example.com"

    def test_attachment_included(self, temp_resume):
        """Test that the resume is attached to the message."""
        raw_message, _ = create_message(
            to_email="test@example.com",
            salutation="Test",
            company="Test",
            template="Hello",
            resume_path=temp_resume,
            subject="Test",
        )

        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        msg = email.message_from_bytes(decoded, policy=policy.default)

        # Should be multipart
        assert msg.is_multipart()

        # Should have an attachment
        attachments = [
            part for part in msg.walk() if part.get_content_disposition() == "attachment"
        ]
        assert len(attachments) == 1

        # Attachment should have the filename
        assert attachments[0].get_filename() is not None

    def test_attachment_uses_original_filename(self, temp_resume):
        """Test that attachment uses the original filename from the path."""
        raw_message, _ = create_message(
            to_email="test@example.com",
            salutation="Test",
            company="Test",
            template="Hello",
            resume_path=temp_resume,
            subject="Test",
        )

        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        msg = email.message_from_bytes(decoded, policy=policy.default)

        attachments = [
            part for part in msg.walk() if part.get_content_disposition() == "attachment"
        ]
        filename = attachments[0].get_filename()

        # Should match the basename of the temp file
        assert filename == os.path.basename(temp_resume)


class TestMIMEEncoding:
    """Tests specifically for MIME encoding behavior."""

    def test_raw_mime_content_no_unwanted_breaks(self, temp_resume):
        """Test that the raw MIME content doesn't have unwanted line breaks in text."""
        # Use a French template similar to the user's real template
        template = """Bonjour {salutation},

Actuellement étudiant en deuxième année de BUT Mesures Physiques (parcours Technique d'Instrumentation) à l'IUT Grand-Ouest Normandie de Caen, je suis à la recherche d'un stage de 3 mois, à débuter à partir d'avril 2026.

Je suis particulièrement intéressé par {company} afin d'y mettre en œuvre mes compétences en métrologie et instrumentation et de mieux appréhender le monde professionnel.

Cordialement"""

        raw_message, body = create_message(
            to_email="test@example.com",
            salutation="Monsieur Mufang",
            company="Inbolt",
            template=template,
            resume_path=temp_resume,
            subject="Candidature Stage",
        )

        # The body should have the expected content
        assert "Monsieur Mufang" in body
        assert "Inbolt" in body

        # Check the body for unwanted line breaks in the middle of words
        # These are the kinds of breaks RFC 2822 encoding might add
        problematic_patterns = [
            "Instru\nmentation",
            "métrolo\ngie",
            "particuliè\nrement",
            "recher\nche",
            "profes\nsionnel",
        ]
        for pattern in problematic_patterns:
            assert pattern not in body, f"Found unwanted break: {pattern}"

        # Now examine the raw MIME message
        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        raw_str = decoded.decode("utf-8", errors="replace")

        # Print for debugging (will show in pytest output on failure)
        print("=== RAW MIME MESSAGE ===")
        print(raw_str[:2000])
        print("========================")

    def test_always_uses_base64_encoding(self, temp_resume):
        """Test that emails always use base64 encoding, not quoted-printable."""
        # Use French text that might trigger quoted-printable on some systems
        template = """Bonjour {salutation},

Actuellement étudiant en deuxième année, je suis à la recherche d'un stage.

Cordialement"""

        raw_message, _ = create_message(
            to_email="test@example.com",
            salutation="Monsieur Test",
            company="TestCorp",
            template=template,
            resume_path=temp_resume,
            subject="Test",
        )

        # Decode and check the Content-Transfer-Encoding
        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        msg = email.message_from_bytes(decoded, policy=policy.default)

        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                cte = part.get("Content-Transfer-Encoding", "").lower()
                assert cte == "base64", f"Expected base64 encoding, got {cte}"
                break

    def test_compare_body_with_decoded_email(self, temp_resume):
        """Compare the returned body with what gets decoded from the MIME message."""
        template = "Hello {salutation}, welcome to {company}. This is a test message."

        raw_message, body = create_message(
            to_email="test@example.com",
            salutation="Mr Test",
            company="TestCorp",
            template=template,
            resume_path=temp_resume,
            subject="Test",
        )

        # Decode the message
        decoded = base64.urlsafe_b64decode(raw_message["raw"])
        msg = email.message_from_bytes(decoded, policy=policy.default)

        # Get the text part
        email_body = None
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                email_body = part.get_content()
                break

        # The decoded email body should match the original body
        # (allowing for trailing newline differences)
        assert email_body is not None
        assert body.strip() == email_body.strip(), (
            f"Body mismatch:\nOriginal: {repr(body)}\nDecoded: {repr(email_body)}"
        )


class TestSendEmail:
    """Tests for the send_email function with mocked Gmail service."""

    def test_send_email_success(self):
        """Test successful email sending."""
        mock_service = MagicMock()
        mock_service.users().messages().send().execute.return_value = {"id": "123"}

        message = {"raw": "dGVzdA=="}  # base64 encoded "test"

        # Should not raise
        send_email(mock_service, message, "test@example.com")

        # Verify the API was called correctly
        mock_service.users().messages().send.assert_called_with(userId="me", body=message)

    def test_send_email_api_error(self):
        """Test email sending with API error."""
        from googleapiclient.errors import HttpError

        mock_service = MagicMock()
        mock_response = MagicMock()
        mock_response.status = 400
        mock_response.reason = "Bad Request"
        mock_service.users().messages().send().execute.side_effect = HttpError(
            mock_response, b"Error"
        )

        message = {"raw": "dGVzdA=="}

        with pytest.raises(HttpError):
            send_email(mock_service, message, "test@example.com")


class TestEmailServiceWithMock:
    """Tests for EmailService with mocked Gmail."""

    def test_send_emails_stream_with_mock(self, test_db, test_user, test_recipient, test_template):
        """Test email sending stream with mocked Gmail service."""
        import json
        import shutil

        from config import settings
        from database import Recipient, User
        from services.email_service import EmailService

        db = test_db()

        # Link recipient to user
        user = db.query(User).filter(User.id == test_user.id).first()
        recipient = db.query(Recipient).filter(Recipient.id == test_recipient.id).first()
        user.recipients.append(recipient)
        db.commit()

        # Create temp credentials and resume
        user_data_dir = settings.get_user_data_dir(test_user.id)
        os.makedirs(user_data_dir, exist_ok=True)

        creds_path = settings.get_credentials_path(test_user.id)
        os.makedirs(os.path.dirname(creds_path), exist_ok=True)
        with open(creds_path, "w") as f:
            f.write('{"installed": {"client_id": "test"}}')

        resume_path = os.path.join(user_data_dir, "test_resume.pdf")
        with open(resume_path, "wb") as f:
            f.write(b"%PDF-1.4 test")

        token_path = settings.get_token_path(test_user.id)
        with open(token_path, "w") as f:
            f.write('{"token": "test", "refresh_token": "test"}')

        try:
            email_service = EmailService(db)

            # Mock the Gmail authentication
            with patch("services.email_service.authenticate_gmail") as mock_auth:
                mock_service = MagicMock()
                mock_service.users().messages().send().execute.return_value = {"id": "123"}
                mock_auth.return_value = mock_service

                results = list(
                    email_service.send_emails_stream(
                        user_id=test_user.id,
                        recipient_ids=[test_recipient.id],
                        subject="Test Subject",
                        dry_run=False,
                    )
                )

                # Should have sent one email
                assert len(results) == 1
                result = json.loads(results[0])
                assert result["status"] == "sent"
                assert result["email"] == test_recipient.email

        finally:
            # Cleanup
            db.close()
            if os.path.exists(creds_path):
                os.remove(creds_path)
            if os.path.exists(token_path):
                os.remove(token_path)
            if os.path.exists(user_data_dir):
                shutil.rmtree(user_data_dir)
