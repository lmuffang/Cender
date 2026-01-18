"""Pydantic models for API request/response schemas."""

import datetime
from pydantic import BaseModel, EmailStr, ConfigDict


class UserCreate(BaseModel):
    username: str
    email: EmailStr


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr


class RecipientCreate(BaseModel):
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None


class RecipientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str | None
    last_name: str | None
    salutation: str | None
    company: str | None


class TemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    content: str
    subject: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class TemplateUpdate(BaseModel):
    content: str
    subject: str


class EmailPreview(BaseModel):
    email: str
    subject: str
    body: str


class EmailLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    recipient_id: int | None
    recipient_email: str
    subject: str
    status: str
    sent_at: datetime.datetime
    error_message: str | None


class SendEmailsRequest(BaseModel):
    recipient_ids: list[int]
    subject: str
    dry_run: bool = False


class GmailAuthCompleteRequest(BaseModel):
    auth_code: str


class AITemplateRequest(BaseModel):
    user_context: str | None = None


class AITemplateResponse(BaseModel):
    content: str
    subject: str
    model_used: str


class OllamaStatusResponse(BaseModel):
    available: bool
    model: str
    model_loaded: bool
    error: str | None = None
