import os
import shutil
import tempfile

import pytest

from api.dependencies import get_db
from database import Base, EmailLog, EmailStatus, Recipient, Template, User
from fastapi.testclient import TestClient
from main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(scope="function")
def test_db():
    """Create a temporary database for testing"""
    # Create temporary directory for test database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    test_engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    yield TestingSessionLocal

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture(scope="function")
def client(test_db):
    """Create a test client with test database"""

    def override_get_db():
        db = test_db()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_db):
    """Create a test user"""
    db = test_db()
    user = User(username="testuser", email="test@example.com")
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()
    return user


@pytest.fixture
def test_recipient(test_db):
    """Create a test recipient"""
    db = test_db()
    recipient = Recipient(
        email="recipient@example.com",
        first_name="John",
        last_name="Doe",
        company="Test Company",
    )
    db.add(recipient)
    db.commit()
    db.refresh(recipient)
    db.close()
    return recipient


@pytest.fixture
def test_template(test_db, test_user):
    """Create a test template for a user"""
    db = test_db()
    template = Template(
        user_id=test_user.id,
        content="Hello {salutation}, welcome to {company}!",
        subject="Testing Welcome",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    db.close()
    return template
