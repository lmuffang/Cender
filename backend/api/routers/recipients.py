"""Recipient management endpoints."""

from fastapi import APIRouter, Depends, UploadFile, File, Query
from sqlalchemy.orm import Session
import pandas as pd

from database import Recipient
from api.schemas import RecipientCreate, RecipientResponse
from api.dependencies import get_db, get_user_service, get_recipient_service
from exceptions import ValidationError, CSVParseError
from utils.logger import logger

router = APIRouter(tags=["recipients"])


@router.post("/recipients/", response_model=RecipientResponse)
async def create_recipient(recipient: RecipientCreate, db: Session = Depends(get_db)):
    """Create a new recipient."""
    recipient_service = get_recipient_service(db)
    try:
        return recipient_service.create(
            email=recipient.email,
            first_name=recipient.first_name,
            last_name=recipient.last_name,
            company=recipient.company,
        )
    except ValueError as e:
        raise ValidationError(str(e))


@router.get("/recipients/{recipient_id}", response_model=RecipientResponse)
async def get_recipient(recipient_id: int, db: Session = Depends(get_db)):
    """Get a specific recipient."""
    recipient_service = get_recipient_service(db)
    return recipient_service.get_by_id(recipient_id)


@router.get("/users/{user_id}/recipients", response_model=list[RecipientResponse])
async def list_recipients(
    user_id: int,
    used: bool | None = Query(None, description="Filter by usage status"),
    db: Session = Depends(get_db),
):
    """List recipients for a user, optionally filtered by usage."""
    recipient_service = get_recipient_service(db)
    return recipient_service.get_by_user(user_id, used)


@router.post("/users/{user_id}/recipients-csv")
async def import_recipients_csv(
    user_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Parse CSV and create/merge recipients for a user."""
    user_service = get_user_service(db)
    user = user_service.get_by_id(user_id)
    recipient_service = get_recipient_service(db)

    try:
        content = await file.read()
        df = pd.read_csv(pd.io.common.BytesIO(content), dtype=str)

        created = 0
        updated = 0
        linked = 0
        skipped = []

        for row_num, row in df.iterrows():
            email = row.get("Email", "")
            if not isinstance(email, str) or not email or not email.strip():
                skipped.append({"row": row_num + 2, "reason": "Missing or empty email"})  # +2 for header + 0-index
                continue
            email = email.strip()

            # Basic email validation
            if "@" not in email or "." not in email:
                skipped.append({"row": row_num + 2, "reason": f"Invalid email format: {email}"})
                continue
            recipient_data = {"First Name": "", "Last Name": "", "Company": ""}
            for key in recipient_data.keys():
                value = row.get(key)
                if not isinstance(value, str) or not value:
                    value = ""  # is empty, NaN
                recipient_data[key] = value.strip()

            # Support "Company Name" as an alternative to "Company"
            if not recipient_data["Company"]:
                company_name = row.get("Company Name")
                if isinstance(company_name, str) and company_name:
                    recipient_data["Company"] = company_name.strip()

            # Find existing recipient
            recipient = db.query(Recipient).filter(Recipient.email == email).one_or_none()

            if recipient:
                # Merge missing info only
                changed = False
                keys_attribute_map = {
                    "First Name": "first_name",
                    "Last Name": "last_name",
                    "Company": "company",
                }
                for key, attribute in keys_attribute_map.items():
                    if recipient_data.get(key) and not getattr(recipient, attribute):
                        setattr(recipient, attribute, recipient_data.get(key))
                        changed = True
                if changed:
                    updated += 1
            else:
                # Create new recipient
                try:
                    recipient = recipient_service.create(
                        email=email,
                        first_name=recipient_data["First Name"] or None,
                        last_name=recipient_data["Last Name"] or None,
                        company=recipient_data["Company"] or None,
                    )
                    created += 1
                except ValueError:
                    # Recipient already exists (race condition)
                    recipient = db.query(Recipient).filter(Recipient.email == email).first()
                    updated += 1

            # Link recipient to user if not already linked
            if recipient not in user.recipients:
                recipient_service.link_to_user(user_id, recipient.id)
                linked += 1

        return {
            "created": created,
            "updated": updated,
            "linked": linked,
            "total": created + updated,
            "skipped": skipped,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error parsing CSV: {e}", exc_info=True)
        raise CSVParseError(f"Error parsing CSV: {str(e)}")


@router.delete("/users/{user_id}/recipients")
async def delete_user_recipients(user_id: int, db: Session = Depends(get_db)):
    """
    Remove all recipients from a user.

    This unlinks the recipients from the user but does not delete the
    recipients themselves (they may be linked to other users).
    """
    recipient_service = get_recipient_service(db)
    count = recipient_service.unlink_all_from_user(user_id)
    return {
        "message": f"Removed {count} recipients from user",
        "count": count,
    }
