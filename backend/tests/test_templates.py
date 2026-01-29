import pytest

from fastapi import status


def test_get_template_default(client, test_user):
    """Test getting default template when user has no template"""
    response = client.get(f"/users/{test_user.id}/template")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "content" in data
    assert "subject" in data
    assert "{salutation}" in data["content"]
    assert "{company}" in data["content"]


def test_create_template(client, test_user):
    """Test creating a template for a user"""
    template_content = "Hello {salutation}, this is a test for {company}!"
    template_subject = "Test Subject"
    response = client.post(
        f"/users/{test_user.id}/template",
        json={"content": template_content, "subject": template_subject},
    )
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]
    data = response.json()
    assert data["content"] == template_content
    assert data["subject"] == template_subject
    assert data["user_id"] == test_user.id


def test_update_template(client, test_user, test_template):
    """Test updating an existing template"""
    new_content = "Updated template for {salutation} at {company}!"
    new_subject = "Updated Subject"
    response = client.post(
        f"/users/{test_user.id}/template",
        json={"content": new_content, "subject": new_subject},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["content"] == new_content
    assert data["subject"] == new_subject
    assert data["id"] == test_template.id


def test_get_template(client, test_user, test_template):
    """Test getting a saved template"""
    response = client.get(f"/users/{test_user.id}/template")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["content"] == test_template.content
    assert data["subject"] == test_template.subject


def test_template_user_not_found(client):
    """Test template operations with non-existent user"""
    response = client.get("/users/99999/template")
    assert response.status_code == status.HTTP_404_NOT_FOUND

    response = client.post(
        "/users/99999/template", json={"content": "Test", "subject": "Test Subject"}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
