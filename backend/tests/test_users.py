import pytest
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
