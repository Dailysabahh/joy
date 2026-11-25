"""Calls and typed chats a voice agent has already had, and the people on them."""
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

from database.db import SessionLocal
from database.models import VoiceAgent, VoiceChat, VoiceContact, VoiceTurn

logger = logging.getLogger("joy.call_log")


def _now():
    return datetime.now(timezone.utc)


def _view(chat: VoiceChat):
    turns = [
        SimpleNamespace(role=turn.role, text=turn.text, created_at=turn.created_at)
        for turn in list(chat.turns)
    ]
    return SimpleNamespace(
        id=chat.id,
        agent_id=chat.agent_id,
        contact_id=chat.contact_id,
        kind=chat.kind or "call",
        started_at=chat.started_at,
        ended_at=chat.ended_at,
        turns=turns,
    )


def open_chat(agent_token: str, kind: str = "call") -> str | None:
    db = SessionLocal()
    try:
        agent = db.query(VoiceAgent).filter(VoiceAgent.token == agent_token).first()
        if not agent:
            return None
        contact = VoiceContact(agent_id=agent.id, name="Caller" if kind != "chat" else "Visitor")
        db.add(contact)
        db.flush()
        chat = VoiceChat(agent_id=agent.id, contact_id=contact.id, kind="chat" if kind == "chat" else "call")
        db.add(chat)
        db.commit()
        return chat.id
    except Exception:
        logger.exception("Could not open a call log")
        db.rollback()
        return None
    finally:
        db.close()


def add_turn(chat_id: str | None, role: str, text: str) -> None:
    if not chat_id or not text.strip():
        return
    db = SessionLocal()
    try:
        chat = db.query(VoiceChat).filter(VoiceChat.id == chat_id).first()
        if not chat:
            return
        db.add(VoiceTurn(chat_id=chat.id, role=role, text=text.strip()))
        if chat.contact_id:
            contact = db.query(VoiceContact).filter(VoiceContact.id == chat.contact_id).first()
            if contact:
                contact.last_active = _now()
        db.commit()
    except Exception:
        logger.exception("Could not save a call turn")
        db.rollback()
    finally:
        db.close()


def history_for(chat_id: str, agent_id: str) -> list[dict] | None:
    db = SessionLocal()
    try:
        chat = db.query(VoiceChat).filter(VoiceChat.id == chat_id, VoiceChat.agent_id == agent_id).first()
        if not chat:
            return None
        return [{"role": turn.role, "text": turn.text} for turn in chat.turns]
    finally:
        db.close()


def close_chat(chat_id: str | None) -> None:
    if not chat_id:
        return
    db = SessionLocal()
    try:
        chat = db.query(VoiceChat).filter(VoiceChat.id == chat_id).first()
        if chat and not chat.ended_at:
            chat.ended_at = _now()
            db.commit()
    except Exception:
        logger.exception("Could not close a call log")
        db.rollback()
    finally:
        db.close()


def chats_for_agents(agent_ids: list[str]) -> list[VoiceChat]:
    if not agent_ids:
        return []
    db = SessionLocal()
    try:
        rows = (
            db.query(VoiceChat)
            .filter(VoiceChat.agent_id.in_(agent_ids))
            .order_by(VoiceChat.started_at.desc())
            .all()
        )
        return [_view(row) for row in rows]
    finally:
        db.close()


def contacts_for_agents(agent_ids: list[str]) -> list[VoiceContact]:
    if not agent_ids:
        return []
    db = SessionLocal()
    try:
        rows = (
            db.query(VoiceContact)
            .filter(VoiceContact.agent_id.in_(agent_ids))
            .order_by(VoiceContact.last_active.desc())
            .all()
        )
        for row in rows:
            db.expunge(row)
        return rows
    finally:
        db.close()


def chat_for_owner(chat_id: str, agent_ids: list[str]) -> VoiceChat | None:
    db = SessionLocal()
    try:
        chat = db.query(VoiceChat).filter(VoiceChat.id == chat_id, VoiceChat.agent_id.in_(agent_ids)).first()
        if not chat:
            return None
        return _view(chat)
    finally:
        db.close()


def contact_for_owner(contact_id: str, agent_ids: list[str]) -> VoiceContact | None:
    db = SessionLocal()
    try:
        contact = (
            db.query(VoiceContact)
            .filter(VoiceContact.id == contact_id, VoiceContact.agent_id.in_(agent_ids))
            .first()
        )
        if contact:
            db.expunge(contact)
        return contact
    finally:
        db.close()


def update_contact(contact_id: str, agent_ids: list[str], name: str, phone: str, email: str, note: str) -> bool:
    db = SessionLocal()
    try:
        contact = (
            db.query(VoiceContact)
            .filter(VoiceContact.id == contact_id, VoiceContact.agent_id.in_(agent_ids))
            .first()
        )
        if not contact:
            return False
        contact.name = name.strip() or "Caller"
        contact.phone = phone.strip() or None
        contact.email = email.strip() or None
        contact.note = note.strip() or None
        db.commit()
        return True
    finally:
        db.close()
