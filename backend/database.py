import functools
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
import os

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/app.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=functools.partial(datetime.now, timezone.utc))


class EmailLog(Base):
    __tablename__ = "email_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)
    recipient_email = Column(String, index=True)
    subject = Column(String)
    status = Column(String)  # sent, failed, skipped
    sent_at = Column(DateTime, default=functools.partial(datetime.now, timezone.utc))
    error_message = Column(Text, nullable=True)


class Template(Base):
    __tablename__ = "templates"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=functools.partial(datetime.now, timezone.utc))
    updated_at = Column(DateTime, default=functools.partial(datetime.now, timezone.utc))