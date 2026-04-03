"""Database models and session management."""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from src.config import settings


class Base(DeclarativeBase):
    pass


class QuestionStatus(str, Enum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    GENERATING = "generating"
    REVIEW = "review"
    APPROVED = "approved"
    POSTING = "posting"
    POSTED = "posted"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    FAILED = "failed"


class AccountHealth(str, Enum):
    HEALTHY = "healthy"
    WARNING = "warning"
    CAPTCHA = "captcha"
    BANNED = "banned"
    RESTING = "resting"


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)  # test_prep, study_abroad, visa, etc.
    topics: Mapped[str] = mapped_column(Text, default="")  # comma-separated Quora topics
    status: Mapped[str] = mapped_column(String(50), default=QuestionStatus.DISCOVERED)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    follower_count: Mapped[int] = mapped_column(Integer, default=0)
    answer_count: Mapped[int] = mapped_column(Integer, default=0)
    discovered_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    answers: Mapped[list["Answer"]] = relationship("Answer", back_populates="question")


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    bio: Mapped[str] = mapped_column(Text, nullable=False)
    expertise_areas: Mapped[str] = mapped_column(Text, nullable=False)  # comma-separated
    writing_style: Mapped[str] = mapped_column(Text, nullable=False)
    quora_email: Mapped[str] = mapped_column(String(300), default="")
    quora_password_ref: Mapped[str] = mapped_column(String(100), default="")  # reference key, not actual password
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    daily_post_count: Mapped[int] = mapped_column(Integer, default=0)
    last_post_date: Mapped[str] = mapped_column(String(10), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    answers: Mapped[list["Answer"]] = relationship("Answer", back_populates="persona")
    accounts: Mapped[list["QuoraAccount"]] = relationship("QuoraAccount", back_populates="persona")


class QuoraAccount(Base):
    __tablename__ = "quora_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    persona_id: Mapped[int] = mapped_column(Integer, ForeignKey("personas.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(300), nullable=False)
    health: Mapped[str] = mapped_column(String(50), default=AccountHealth.HEALTHY)
    posts_today: Mapped[int] = mapped_column(Integer, default=0)
    total_posts: Mapped[int] = mapped_column(Integer, default=0)
    last_active: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    browser_profile_path: Mapped[str] = mapped_column(String(500), default="")
    proxy_url: Mapped[str] = mapped_column(String(500), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    persona: Mapped["Persona"] = relationship("Persona", back_populates="accounts")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("questions.id"), nullable=False)
    persona_id: Mapped[int] = mapped_column(Integer, ForeignKey("personas.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="draft")  # draft, approved, posted, rejected
    reviewer_notes: Mapped[str] = mapped_column(Text, default="")
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    question: Mapped["Question"] = relationship("Question", back_populates="answers")
    persona: Mapped["Persona"] = relationship("Persona", back_populates="answers")


class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str] = mapped_column(Text, default="")
    persona_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("personas.id"), nullable=True)
    question_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("questions.id"), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


# Synchronous engine for simplicity (can upgrade to async later)
db_url = settings.database_url.replace("sqlite+aiosqlite:", "sqlite:")
engine = create_engine(db_url, echo=False)


# Enable WAL mode for SQLite for better concurrent access
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


SessionLocal = sessionmaker(bind=engine)


def init_db():
    """Create all tables."""
    Base.metadata.create_all(engine)


def get_db() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise
