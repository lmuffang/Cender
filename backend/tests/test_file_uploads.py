import pytest
from fastapi import status
import io


def test_upload_credentials(client, test_user):
    """Test uploading Gmail credentials"""
    # Create a fake JSON file
    fake_credentials = b'{"type": "service_account", "project_id": "test"}'
    files = {"file": ("credentials.json", io.BytesIO(fake_credentials), "application/json")}
    
    response = client.post(
        f"/users/{test_user.id}/credentials",
        files=files
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "message" in data


def test_upload_credentials_user_not_found(client):
    """Test uploading credentials for non-existent user"""
    fake_credentials = b'{"type": "service_account"}'
    files = {"file": ("credentials.json", io.BytesIO(fake_credentials), "application/json")}
    
    response = client.post(
        "/users/99999/credentials",
        files=files
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_upload_resume(client, test_user):
    """Test uploading resume PDF"""
    # Create a fake PDF file
    fake_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 0\ntrailer\n<< /Size 0 /Root 1 0 R >>\nstartxref\n0\n%%EOF"
    files = {"file": ("resume.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    
    response = client.post(
        f"/users/{test_user.id}/resume",
        files=files
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "message" in data


def test_upload_resume_non_pdf(client, test_user):
    """Test uploading non-PDF file as resume"""
    fake_file = b"This is not a PDF"
    files = {"file": ("resume.txt", io.BytesIO(fake_file), "text/plain")}
    
    response = client.post(
        f"/users/{test_user.id}/resume",
        files=files
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_upload_resume_user_not_found(client):
    """Test uploading resume for non-existent user"""
    fake_pdf = b"%PDF-1.4"
    files = {"file": ("resume.pdf", io.BytesIO(fake_pdf), "application/pdf")}
    
    response = client.post(
        "/users/99999/resume",
        files=files
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND

