"""User service layer."""
from sqlalchemy.orm import Session

from database import User
from exceptions import UserNotFoundError
from utils.logger import logger


class UserService:
    """Service for user operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create(self, username: str, email: str) -> User:
        """
        Create a new user.
        
        Args:
            username: Username
            email: Email address
            
        Returns:
            Created user
            
        Raises:
            ValueError: If user with email already exists
        """
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            logger.warning(f"Attempt to create user with existing email: {email}")
            raise ValueError(f"User with email {email} already exists")
        
        user = User(username=username, email=email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        logger.info(f"Created user: {user.id} ({username})")
        return user
    
    def get_by_id(self, user_id: int) -> User:
        """
        Get user by ID.
        
        Args:
            user_id: User ID
            
        Returns:
            User instance
            
        Raises:
            UserNotFoundError: If user not found
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise UserNotFoundError(f"User with id {user_id} not found")
        return user
    
    def get_all(self) -> list[User]:
        """
        Get all users.
        
        Returns:
            List of all users
        """
        return self.db.query(User).all()
    
    def get_by_email(self, email: str) -> User | None:
        """
        Get user by email.
        
        Args:
            email: Email address
            
        Returns:
            User instance or None if not found
        """
        return self.db.query(User).filter(User.email == email).first()

