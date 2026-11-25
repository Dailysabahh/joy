"""
Demo bot engine — generates demo bot records and serves demo chat API.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from database.models import BotOrder, DemoBot


def create_demo_bot(db: Session, order_id: str) -> DemoBot:
    """Create a DemoBot linked to an order. Expires in 7 days."""
    existing = db.query(DemoBot).filter(DemoBot.order_id == order_id).first()
    if existing:
        return existing

    demo = DemoBot(
        order_id=order_id,
        token=str(uuid.uuid4()),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        active=True,
    )
    db.add(demo)
    db.flush()
    return demo


def get_demo_by_token(db: Session, token: str) -> DemoBot | None:
    return db.query(DemoBot).filter(DemoBot.token == token).first()


def get_order_dict(order: BotOrder) -> dict:
    """Convert a BotOrder to a plain dict for the brain."""
    return {
        "bot_name": order.bot_name,
        "industry": order.industry,
        "business_name": order.business_name,
        "business_details": order.business_details,
        "personality": order.personality,
        "tone": order.tone,
        "custom_instructions": order.custom_instructions,
    }
