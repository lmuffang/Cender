"""Template service layer."""

import re

from database import Template
from exceptions import TemplateNotFoundError, UserNotFoundError, ValidationError
from sqlalchemy.orm import Session
from utils.logger import logger

from services.user_service import UserService

# Valid placeholders that can be used in templates
VALID_PLACEHOLDERS = {"salutation", "company", "company_name"}


def validate_template_placeholders(content: str) -> list[str]:
    """
    Validate that template only uses known placeholders.

    Returns list of invalid placeholder names found.
    """
    found_placeholders = re.findall(r"\{(\w+)\}", content)
    return [p for p in found_placeholders if p not in VALID_PLACEHOLDERS]


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
            return {"content": template.content, "subject": template.subject}

        # Default template
        default = (
            "Bonjour {salutation},\n\n"
            "Je me permets de vous contacter concernant une opportunité au sein de {company}. "
            "Vous trouverez ci-joint mon CV.\n\n"
            "Cordialement,\n"
            "Votre Nom"
        )
        return {"content": default, "subject": "Candidature spontanée"}

    def create_or_update(self, user_id: int, content: str, subject: str) -> Template:
        """
        Create or update user's template.

        Args:
            user_id: User ID
            content: Template content
            subject: Template subject

        Returns:
            Template instance

        Raises:
            UserNotFoundError: If user not found
            ValidationError: If template contains invalid placeholders
        """
        # Verify user exists
        self.user_service.get_by_id(user_id)

        # Validate placeholders
        invalid_placeholders = validate_template_placeholders(content)
        if invalid_placeholders:
            invalid_list = ", ".join(f"{{{p}}}" for p in invalid_placeholders)
            raise ValidationError(
                f"Invalid placeholder(s): {invalid_list}. "
                f"Valid placeholders are: {{salutation}}, {{company}}, {{company_name}}"
            )

        template = self.db.query(Template).filter(Template.user_id == user_id).first()
        if template:
            template.content = content
            template.subject = subject
            logger.info(f"Updated template for user {user_id}")
        else:
            template = Template(user_id=user_id, content=content, subject=subject)
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
