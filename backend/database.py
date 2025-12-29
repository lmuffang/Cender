import enum
import os
import functools
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    create_engine,
    String,
    DateTime,
    Table,
    Enum,
    Text,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


class Base(DeclarativeBase):
    pass


class EmailStatus(str, enum.Enum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"

# Association Table fro Many to many User <> Recipient
user_recipients = Table(
    "user_recipients",
    Base.metadata,
    mapped_column(
        "user_id",
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    mapped_column(
        "recipient_id",
        ForeignKey("recipients.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

# Models
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    recipients: Mapped[list["Recipient"]] = relationship(
        secondary=user_recipients,
        back_populates="users",
    )

    emails: Mapped[list["EmailLog"]] = relationship(
        cascade="all, delete-orphan"
    )

    template: Mapped["Template"] = relationship(
        uselist=False,
        cascade="all, delete-orphan"
    )

class EmailLog(Base):
    __tablename__ = "email_logs"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    recipient_id: Mapped[int | None] = mapped_column(
        ForeignKey("recipients.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    recipient_email: Mapped[str] = mapped_column(nullable=False)
    subject: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus, name="email_status"),
        nullable=False,
    )

    sent_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    error_message: Mapped[str | None] = mapped_column(Text)

    # Relationships
    user: Mapped["User"] = relationship(
        back_populates="emails"
    )

    recipient: Mapped["Recipient"] = relationship(
        back_populates="emails"
    )



class Template(Base):
    __tablename__ = "templates"

    id: Mapped[int] = mapped_column(primary_key=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
    )

    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=functools.partial(datetime.now, timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=functools.partial(datetime.now, timezone.utc),
        onupdate=functools.partial(datetime.now, timezone.utc),
    )

    user: Mapped["User"] = relationship(back_populates="template")

class Recipient(Base):
    __tablename__ = "recipients"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(index=True, nullable=False, unique=True)
    first_name: Mapped[str | None]
    last_name: Mapped[str | None]
    salutation: Mapped[str | None]
    company: Mapped[str | None]

    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    users: Mapped[list["User"]] = relationship(
        secondary=user_recipients,
        back_populates="recipients",
    )

    emails: Mapped[list["EmailLog"]] = relationship(
        back_populates="recipient"
    )

