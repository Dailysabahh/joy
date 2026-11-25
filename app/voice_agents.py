"""Saved voice agents that answer on a website or a phone line."""
from app.gemini_voices import manner_instruction, normalize_manner, normalize_tone, normalize_voice, tone_instruction
from database.db import SessionLocal
from database.models import VoiceAgent


def _session():
    return SessionLocal()


def create_agent(
    name: str,
    business_name: str,
    description: str,
    greeting: str,
    channel: str,
    phone_number: str | None,
    role: str | None = None,
    industry: str | None = None,
    website: str | None = None,
    objective: str | None = None,
    voice: str | None = None,
    tone: str | None = None,
    manner: str | None = None,
    account_id: str | None = None,
) -> VoiceAgent:
    db = _session()
    try:
        agent = VoiceAgent(
            name=name.strip(),
            business_name=business_name.strip(),
            description=description.strip(),
            greeting=greeting.strip(),
            channel="phone" if channel == "phone" else "website",
            phone_number=(phone_number or "").strip() or None,
            role=(role or "").strip() or None,
            industry=(industry or "").strip() or None,
            website=(website or "").strip() or None,
            objective=(objective or "").strip() or None,
            voice=normalize_voice(voice),
            tone=normalize_tone(tone),
            manner=normalize_manner(manner),
            account_id=(account_id or "").strip() or None,
        )
        db.add(agent)
        db.commit()
        db.refresh(agent)
        db.expunge(agent)
        return agent
    finally:
        db.close()


def get_agent(token: str) -> VoiceAgent | None:
    db = _session()
    try:
        agent = db.query(VoiceAgent).filter(VoiceAgent.token == token).first()
        if agent:
            db.expunge(agent)
        return agent
    finally:
        db.close()


def update_agent(token: str, **fields) -> VoiceAgent | None:
    allowed = {
        "name", "business_name", "description", "greeting",
        "role", "industry", "website", "objective", "phone_number", "channel",
        "voice", "tone", "manner",
    }
    db = _session()
    try:
        agent = db.query(VoiceAgent).filter(VoiceAgent.token == token).first()
        if not agent:
            return None
        for key, value in fields.items():
            if key not in allowed:
                continue
            cleaned = (value or "").strip()
            if key == "voice":
                agent.voice = normalize_voice(cleaned)
                continue
            if key == "tone":
                agent.tone = normalize_tone(cleaned)
                continue
            if key == "manner":
                agent.manner = normalize_manner(cleaned)
                continue
            setattr(agent, key, cleaned or None)
        agent.channel = "phone" if agent.phone_number else "website"
        db.commit()
        db.refresh(agent)
        db.expunge(agent)
        return agent
    finally:
        db.close()


def claim_agent(token: str, account_id: str) -> VoiceAgent | None:
    db = _session()
    try:
        agent = db.query(VoiceAgent).filter(VoiceAgent.token == token).first()
        if not agent:
            return None
        if not agent.account_id:
            agent.account_id = account_id
            db.commit()
            db.refresh(agent)
        db.expunge(agent)
        return agent
    finally:
        db.close()


def agents_for(account_id: str) -> list[VoiceAgent]:
    db = _session()
    try:
        rows = (
            db.query(VoiceAgent)
            .filter(VoiceAgent.account_id == account_id)
            .order_by(VoiceAgent.created_at.desc())
            .all()
        )
        for row in rows:
            db.expunge(row)
        return rows
    finally:
        db.close()


def update_phone(token: str, phone_number: str) -> VoiceAgent | None:
    db = _session()
    try:
        agent = db.query(VoiceAgent).filter(VoiceAgent.token == token).first()
        if not agent:
            return None
        agent.phone_number = phone_number.strip()
        agent.channel = "phone"
        db.commit()
        db.refresh(agent)
        db.expunge(agent)
        return agent
    finally:
        db.close()


def save_studio(token: str, form) -> VoiceAgent | None:
    from app.studio_profile import apply_form

    db = _session()
    try:
        agent = db.query(VoiceAgent).filter(VoiceAgent.token == token).first()
        if not agent:
            return None
        apply_form(agent, form)
        db.commit()
        db.refresh(agent)
        db.expunge(agent)
        return agent
    finally:
        db.close()


def instructions_for(agent: VoiceAgent) -> str:
    from app.studio_profile import knowledge_text

    where = "the business website"
    if agent.channel == "phone" and agent.phone_number:
        where = f"the phone number {agent.phone_number}"
    return f"""# Role
You are {agent.name}, the voice agent for {agent.business_name}.
You are speaking on a live call from {where}.

# Language
- Speak only English. Every word you say is English.
- If the caller speaks another language, understand them and still answer in English.
- Never switch language or mix languages.

# Personality and Tone
- Sound like a person who picked up the phone, not a presenter.
- {tone_instruction(agent.tone)}
- Use contractions.
- {manner_instruction(agent.manner)}
- Ask one question at a time.
- Answer the specific thing they asked. Do not recite a whole menu or every service.

# Business
Role: {agent.role or "receptionist"}
Industry: {agent.industry or "not specified"}
Objective: {agent.objective or "Help the caller and take the next step."}
Website: {agent.website or "not provided"}
{agent.description}

{knowledge_text(agent)}

# Greeting
When the call starts, say this in English and then wait: {agent.greeting}
""".strip()


def greeting_for(agent: VoiceAgent) -> str:
    return (
        "The caller just connected. Say only this, in English, then wait: "
        + agent.greeting
    )
