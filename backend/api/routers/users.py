"""User management endpoints."""

from exceptions import ValidationError
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_db, get_user_service
from api.schemas import UserCreate, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user."""
    user_service = get_user_service(db)
    try:
        return user_service.create(user.username, user.email)
    except ValueError as e:
        raise ValidationError(str(e))


@router.get("/", response_model=list[UserResponse])
async def list_users(db: Session = Depends(get_db)):
    """List all users."""
    user_service = get_user_service(db)
    return user_service.get_all()


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: Session = Depends(get_db)):
    """Get a specific user."""
    user_service = get_user_service(db)
    return user_service.get_by_id(user_id)


@router.delete("/{user_id}")
async def delete_user(user_id: int, db: Session = Depends(get_db)):
    """
    Delete a user and all associated data.

    This will permanently delete:
    - User's email template
    - User's email logs
    - User's recipient links (recipients themselves are kept)
    - User's files (credentials, token, resume)
    """
    user_service = get_user_service(db)
    return user_service.delete(user_id)
