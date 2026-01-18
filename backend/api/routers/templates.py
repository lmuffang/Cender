"""Template management endpoints."""

import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas import TemplateResponse, TemplateUpdate
from api.dependencies import get_db, get_template_service
from exceptions import TemplateNotFoundError

router = APIRouter(prefix="/users/{user_id}", tags=["templates"])


@router.get("/template", response_model=TemplateResponse)
async def get_template(user_id: int, db: Session = Depends(get_db)):
    """Get user's template or return default."""
    template_service = get_template_service(db)
    template_data = template_service.get_or_default(user_id)

    # Try to get actual template from DB
    try:
        template = template_service.get(user_id)
        return template
    except TemplateNotFoundError:
        # Return default template info (not saved in DB)
        return TemplateResponse(
            id=0,
            user_id=user_id,
            content=template_data["content"],
            subject=template_data["subject"],
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )


@router.post("/template", response_model=TemplateResponse)
async def create_or_update_template(
    user_id: int, template_update: TemplateUpdate, db: Session = Depends(get_db)
):
    """Create or update user's template."""
    template_service = get_template_service(db)
    return template_service.create_or_update(user_id, template_update.content, template_update.subject)


@router.put("/template", response_model=TemplateResponse)
async def update_template(
    user_id: int, template_update: TemplateUpdate, db: Session = Depends(get_db)
):
    """Update user's template (alias for POST)."""
    return await create_or_update_template(user_id, template_update, db)
