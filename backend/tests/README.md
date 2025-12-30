# Backend API Tests

This directory contains pytest tests for the backend API.

## Running Tests

From the `backend/` directory:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_users.py

# Run a specific test
pytest tests/test_users.py::test_create_user

# Run with coverage
pytest --cov=. --cov-report=html
```

## Test Structure

- `conftest.py` - Shared fixtures and test configuration
- `test_users.py` - User CRUD operations
- `test_templates.py` - Template management
- `test_recipients.py` - Recipient management and CSV import
- `test_email_operations.py` - Email preview, sending, and logs
- `test_file_uploads.py` - File upload endpoints (credentials, resume)

## Test Database

Tests use a temporary SQLite database that is created and destroyed for each test session. This ensures tests don't interfere with each other or with the development database.

