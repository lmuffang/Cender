"""Template service layer."""

from sqlalchemy.orm import Session

from database import Template
from exceptions import TemplateNotFoundError, UserNotFoundError
from services.user_service import UserService
from utils.logger import logger


class TemplateService:
    """Service for template operations."""

    def __init__(self, db: Session):
        self.db = db
        self.user_service = UserService(db)

    def get_or_default(self, user_id: int) -> dict:
        """
        Get user's template or return default.

        Args:
            user_id: User ID

        Returns:
            Dictionary with template content
        """
        # Verify user exists
        self.user_service.get_by_id(user_id)

        template = self.db.query(Template).filter(Template.user_id == user_id).first()
        if template:
            return {"content": template.content}

        # Default template
        default = (
            "Bonjour {salutation},\n\n"
            "Je me permets de vous contacter concernant une opportunité au sein de {company}. "
            "Vous trouverez ci-joint mon CV.\n\n"
            "Cordialement,\n"
            "Votre Nom"
        )
        return {"content": default}

    def create_or_update(self, user_id: int, content: str) -> Template:
        """
        Create or update user's template.

        Args:
            user_id: User ID
            content: Template content

        Returns:
            Template instance

        Raises:
            UserNotFoundError: If user not found
        """
        # Verify user exists
        self.user_service.get_by_id(user_id)

        template = self.db.query(Template).filter(Template.user_id == user_id).first()
        if template:
            template.content = content
            logger.info(f"Updated template for user {user_id}")
        else:
            template = Template(user_id=user_id, content=content)
            self.db.add(template)
            logger.info(f"Created template for user {user_id}")

        self.db.commit()
        self.db.refresh(template)
        return template

    def get(self, user_id: int) -> Template:
        """
        Get user's template.

        Args:
            user_id: User ID

        Returns:
            Template instance

        Raises:
            TemplateNotFoundError: If template not found
        """
        template = self.db.query(Template).filter(Template.user_id == user_id).first()
        if not template:
            raise TemplateNotFoundError(f"Template for user {user_id} not found")
        return template
