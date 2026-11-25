import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./joy.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from database.models import (  # noqa: F401
        User, Message, BotOrder, DemoBot, PaymentLead, VoiceAgent,
        VoiceContact, VoiceChat, VoiceTurn,
    )
    Base.metadata.create_all(bind=engine)
    _ensure_voice_agent_columns()
    _ensure_account_columns()
    _ensure_chat_columns()


def _ensure_voice_agent_columns():
    """SQLite create_all does not add columns to a table that already exists."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(voice_agents)")).fetchall()
        names = {row[1] for row in rows}
        for column in ("role", "industry", "website", "objective", "voice", "tone", "manner", "account_id", "profile"):
            if column not in names:
                kind = "TEXT" if column in ("objective", "profile") else "VARCHAR"
                conn.execute(text(f"ALTER TABLE voice_agents ADD COLUMN {column} {kind}"))


def _ensure_account_columns():
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(customer_accounts)")).fetchall()
        if not rows:
            return
        names = {row[1] for row in rows}
        if "access" not in names:
            conn.execute(text("ALTER TABLE customer_accounts ADD COLUMN access VARCHAR"))
        if "trial_ends_at" not in names:
            conn.execute(text("ALTER TABLE customer_accounts ADD COLUMN trial_ends_at DATETIME"))
        if "email_verified" not in names:
            conn.execute(text("ALTER TABLE customer_accounts ADD COLUMN email_verified BOOLEAN"))
        if "verification_code" not in names:
            conn.execute(text("ALTER TABLE customer_accounts ADD COLUMN verification_code VARCHAR"))


def _ensure_chat_columns():
    if not DATABASE_URL.startswith("sqlite"):
        return
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(voice_chats)")).fetchall()
        if not rows:
            return
        names = {row[1] for row in rows}
        if "kind" not in names:
            conn.execute(text("ALTER TABLE voice_chats ADD COLUMN kind VARCHAR"))
