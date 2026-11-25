import uuid
import hashlib
import secrets
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, DateTime, Boolean,
    ForeignKey, Integer, JSON
)
from sqlalchemy.orm import relationship
from database.db import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    phone = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    state = Column(String, default="greeting", nullable=False)
    state_data = Column(JSON, default=dict)
    needs_escalation = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)
    last_active = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    messages = relationship("Message", back_populates="user", cascade="all, delete-orphan")
    bot_orders = relationship("BotOrder", back_populates="user", cascade="all, delete-orphan")
    payment_leads = relationship("PaymentLead", back_populates="user", cascade="all, delete-orphan")
    escalations = relationship("Escalation", back_populates="user", cascade="all, delete-orphan")
    account = relationship("CustomerAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")

    def bump_activity(self):
        self.last_active = _now()

    @property
    def message_count(self):
        return len(self.messages)

    @property
    def short_id(self):
        return self.id[:8].upper()

    @property
    def demo_count(self):
        return sum(1 for o in self.bot_orders if o.status == "completed" and o.demo_bot)


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False)   # "user" | "joy"
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="messages")


class BotOrder(Base):
    __tablename__ = "bot_orders"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    bot_name = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    business_name = Column(String, nullable=True)
    business_details = Column(Text, nullable=True)
    personality = Column(String, default="professional")
    tone = Column(String, default="friendly")
    custom_instructions = Column(Text, nullable=True)
    # status: in_progress | completed | paid
    status = Column(String, default="in_progress")
    created_at = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="bot_orders")
    demo_bot = relationship("DemoBot", back_populates="order", uselist=False, cascade="all, delete-orphan")


class DemoBot(Base):
    __tablename__ = "demo_bots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String, ForeignKey("bot_orders.id"), nullable=False, unique=True)
    token = Column(String, unique=True, nullable=False, default=_uuid)
    created_at = Column(DateTime(timezone=True), default=_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, default=True)

    order = relationship("BotOrder", back_populates="demo_bot")

    @property
    def is_expired(self):
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires


class PaymentLead(Base):
    __tablename__ = "payment_leads"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    plan = Column(String, nullable=False)
    setup_fee = Column(Integer, nullable=False)
    monthly_fee = Column(Integer, nullable=False)
    customer_name = Column(String, nullable=True)
    customer_email = Column(String, nullable=True)
    payment_reference = Column(String, nullable=True)   # set when payment is confirmed
    # status: new | notified | contacted | paid | account_created
    status = Column(String, default="new")
    notified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="payment_leads")


class Escalation(Base):
    __tablename__ = "escalations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    # trigger: human_request | unanswered | frustration | repeat_question
    trigger = Column(String, nullable=False)
    user_message = Column(Text, nullable=True)
    joy_response = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="escalations")


class CustomerAccount(Base):
    __tablename__ = "customer_accounts"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    email = Column(String, nullable=True)
    email_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)
    plan = Column(String, nullable=False)
    access = Column(String, nullable=True)  # new | trial | paid
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    portal_token = Column(String, unique=True, default=_uuid)
    created_at = Column(DateTime(timezone=True), default=_now)

    user = relationship("User", back_populates="account")

    @staticmethod
    def hash_password(plain: str) -> str:
        return hashlib.sha256(plain.encode()).hexdigest()

    @staticmethod
    def generate_password(length: int = 10) -> str:
        alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def check_password(self, plain: str) -> bool:
        return self.password_hash == hashlib.sha256(plain.encode()).hexdigest()


class VoiceAgent(Base):
    __tablename__ = "voice_agents"

    id = Column(String, primary_key=True, default=_uuid)
    token = Column(String, unique=True, nullable=False, default=_uuid, index=True)
    name = Column(String, nullable=False)
    business_name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    greeting = Column(String, nullable=False)
    channel = Column(String, nullable=False, default="website")  # website | phone
    phone_number = Column(String, nullable=True)
    role = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    website = Column(String, nullable=True)
    objective = Column(Text, nullable=True)
    voice = Column(String, nullable=True)
    tone = Column(String, nullable=True)
    manner = Column(String, nullable=True)
    account_id = Column(String, nullable=True, index=True)
    profile = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class VoiceContact(Base):
    __tablename__ = "voice_contacts"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False, default="Caller")
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    last_active = Column(DateTime(timezone=True), default=_now)


class VoiceChat(Base):
    __tablename__ = "voice_chats"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=False, index=True)
    contact_id = Column(String, nullable=True, index=True)
    kind = Column(String, nullable=False, default="call")  # call | chat
    started_at = Column(DateTime(timezone=True), default=_now)
    ended_at = Column(DateTime(timezone=True), nullable=True)

    turns = relationship("VoiceTurn", cascade="all, delete-orphan", order_by="VoiceTurn.id")


class VoiceTurn(Base):
    __tablename__ = "voice_turns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, ForeignKey("voice_chats.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # caller | assistant
    text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    chat = relationship("VoiceChat", back_populates="turns")
