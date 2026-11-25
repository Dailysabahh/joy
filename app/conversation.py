"""
Conversation manager — per-user state machine.

States:
  greeting        → First message ever from this user
  name_collection → Joy greeted; waiting for customer's name
  browsing        → General Q&A about Closer Tech
  building_bot    → Bot builder flow (step-by-step)
  payment_intent  → User wants to buy a plan
  lead_captured   → Name + email collected, admin notified
"""
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.bot_builder import (
    INDUSTRIES,
    PERSONALITIES,
    get_industry_detail_prompt,
    next_step,
    parse_industry_choice,
    parse_personality_choice,
)
from app.joy_brain import detect_intent, get_joy_response, parse_bot_amendment
from database.models import BotOrder, CustomerAccount, Escalation, Message, PaymentLead, User

logger = logging.getLogger(__name__)

PLAN_MAP = {
    "starter":       {"name": "Starter",        "setup_fee": 300,  "monthly_fee": 80},
    "growth":        {"name": "Growth",          "setup_fee": 700,  "monthly_fee": 150},
    "enterprise":    {"name": "Enterprise",      "setup_fee": 1200, "monthly_fee": 500},
    "business_brain":{"name": "Business Brain",  "setup_fee": 1200, "monthly_fee": 300, "requires_consultation": True},
    "1": {"name": "Starter",        "setup_fee": 300,  "monthly_fee": 80},
    "2": {"name": "Growth",         "setup_fee": 700,  "monthly_fee": 150},
    "3": {"name": "Enterprise",     "setup_fee": 1200, "monthly_fee": 500},
    "4": {"name": "Business Brain", "setup_fee": 1200, "monthly_fee": 300, "requires_consultation": True},
}

# Phrases that may signal the user wants a human or is frustrated
_ESCALATION_TRIGGERS = (
    "speak to a human", "real person", "speak to someone", "talk to someone",
    "speak to an agent", "customer service", "this is useless", "you don't understand",
    "you're not helping", "you are not helping", "not helpful", "useless",
    "i want to speak", "connect me", "transfer me",
)

MAX_DEMO_BOTS = 2

_TEST_TRIGGERS = (
    "test run", "test it", "test the bot", "try it", "try the bot", "try my bot",
    "chat with my bot", "talk to my bot", "let me test", "can i test",
    "that's all", "thats all", "that's enough", "build it now",
    "go ahead and build", "ready to test", "want to test", "connect to my bot",
    "let me chat", "start the demo", "launch the bot", "see the bot",
)
_PAY_NOW_TRIGGERS = ("pay now", "checkout", "pay directly", "skip demo", "just pay")


# ── Helpers ───────────────────────────────────────────────────────────────────


def _save_messages(db: Session, user: User, user_text: str, joy_reply: str) -> None:
    db.add(Message(user_id=user.id, role="user", content=user_text))
    db.add(Message(user_id=user.id, role="joy", content=joy_reply))
    user.bump_activity()


def _recent_history(user: User, limit: int = 20) -> list[dict]:
    msgs = sorted(user.messages, key=lambda m: m.timestamp)[-limit:]
    return [{"role": m.role, "content": m.content} for m in msgs]


def _wants_to_test(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in _TEST_TRIGGERS)


def _wants_pay_now(text: str) -> bool:
    t = text.lower()
    return any(trigger in t for trigger in _PAY_NOW_TRIGGERS)


def _has_enough_for_demo(collected: dict) -> bool:
    if not collected.get("bot_name"):
        return False
    return bool(collected.get("business_details") or collected.get("business_name"))


def _gather_build_data(user: User, state_data: dict) -> dict:
    """Merge state_data with recent conversation when the formal steps got out of sync."""
    collected = {
        k: v for k, v in state_data.items()
        if k != "step" and not k.startswith("_")
    }
    recent_user_msgs = [
        m.content for m in sorted(user.messages, key=lambda m: m.timestamp)[-20:]
        if m.role == "user"
    ]
    if not collected.get("business_details"):
        detail_msgs = [m for m in recent_user_msgs if len(m.strip()) > 30]
        if detail_msgs:
            collected["business_details"] = "\n\n".join(detail_msgs[-4:])
    if state_data.get("_industry_description") and not collected.get("business_details"):
        collected["business_details"] = state_data["_industry_description"]
    if not collected.get("business_name") and collected.get("bot_name"):
        collected["business_name"] = collected["bot_name"]
    collected.setdefault("industry", "custom")
    collected.setdefault("personality", "professional")
    return collected


def _get_latest_demo_link(db: Session, user: User) -> str | None:
    import os
    latest_order = (
        db.query(BotOrder)
        .filter(BotOrder.user_id == user.id, BotOrder.status == "completed")
        .order_by(BotOrder.created_at.desc())
        .first()
    )
    if not latest_order or not latest_order.demo_bot:
        return None
    base_url = os.getenv("BASE_URL", "https://joy.aicloser.tech")
    return f"{base_url}/demo/{latest_order.demo_bot.token}"


def _handle_test_request(db: Session, user: User, state_data: dict) -> str:
    """Let the user test their bot — finalize if needed, or return an existing demo link."""
    existing_link = _get_latest_demo_link(db, user)
    if existing_link:
        user.state = "browsing"
        user.state_data = {}
        bot_name = state_data.get("bot_name", "your bot")
        return (
            f"Your demo is ready! 🎉\n\n"
            f"👉 Chat with *{bot_name}* here:\n{existing_link}\n\n"
            f"It's live for 7 days. Test it out and let me know if you'd like any changes."
        )

    collected = _gather_build_data(user, state_data)
    if not _has_enough_for_demo(collected):
        return (
            "I'd love to get your demo ready! I just need a bit more info first.\n\n"
            "What's your business name, and can you share a few details about what the bot should handle?"
        )

    reply = _finalize_bot(db, user, collected)
    return reply


def _check_escalation(db: Session, user: User, text: str, reply: str) -> None:
    """Flag and store escalation triggers."""
    text_lower = text.lower()
    trigger = None
    if any(t in text_lower for t in _ESCALATION_TRIGGERS):
        trigger = "human_request"
    elif any(p in reply.lower() for p in ("i don't have", "i'm not sure", "i cannot", "i do not have information")):
        trigger = "unanswered"
    elif text_lower.count("?") >= 2 or len(text) > 300:
        trigger = "complex_query"

    if trigger:
        db.add(Escalation(
            user_id=user.id,
            trigger=trigger,
            user_message=text[:500],
            joy_response=reply[:500],
        ))
        user.needs_escalation = True


# ── Main entry point ──────────────────────────────────────────────────────────


def handle_message(db: Session, phone: str, text: str) -> str:
    text = text.strip()

    user = db.query(User).filter(User.phone == phone).first()
    if not user:
        user = User(phone=phone, state="greeting", state_data={})
        db.add(user)
        db.flush()

    state = user.state
    state_data = user.state_data or {}

    # ── GREETING ──────────────────────────────────────────────────────────────
    if state == "greeting":
        reply = get_joy_response(text, [], state="greeting", state_data=state_data)
        # Append name request naturally
        reply = reply.rstrip() + "\n\nBefore we get started — what's your name?"
        user.state = "name_collection"
        _save_messages(db, user, text, reply)
        db.commit()
        return reply

    # ── NAME COLLECTION ───────────────────────────────────────────────────────
    if state == "name_collection":
        name = text.strip().split()[0].capitalize()  # take first word as name
        user.name = name
        user.state = "browsing"
        reply = (
            f"Great to meet you, {name}! How can I help you today?\n\n"
            f"I can tell you about our services, give you pricing info, or even build you "
            f"a free demo bot right now so you can see exactly what yours would look like."
        )
        _save_messages(db, user, text, reply)
        db.commit()
        return reply

    # ── BUILDING_BOT ──────────────────────────────────────────────────────────
    if state == "building_bot":
        reply = _handle_bot_building(db, user, text, state_data)
        db.commit()
        return reply

    # ── PAYMENT_INTENT ────────────────────────────────────────────────────────
    if state == "payment_intent":
        reply = _handle_payment_intent(db, user, text, state_data)
        db.commit()
        return reply

    # ── LEAD_CAPTURED ─────────────────────────────────────────────────────────
    if state == "lead_captured":
        user.state = "browsing"
        user.state_data = {}
        reply = get_joy_response(text, _recent_history(user), state="browsing")
        _save_messages(db, user, text, reply)
        db.commit()
        return reply

    # ── BROWSING (default) ────────────────────────────────────────────────────
    intent = detect_intent(text)
    logger.debug("User %s intent: %s", user.short_id, intent)

    if intent == "test_bot" or (_wants_to_test(text) and intent != "build_bot"):
        reply = _handle_test_request(db, user, state_data)
        _save_messages(db, user, text, reply)
        db.commit()
        return reply

    if intent == "build_bot":
        # Check demo bot limit
        if user.demo_count >= MAX_DEMO_BOTS:
            name_part = f"{user.name}, " if user.name else ""
            reply = (
                f"You've already built {MAX_DEMO_BOTS} demo bots — that's the max for the free demo.\n\n"
                f"To get your own live bot deployed and fully customised, {name_part}"
                f"you'll need to pick a plan. Want me to walk you through the options?"
            )
            _save_messages(db, user, text, reply)
            db.commit()
            return reply

        user.state = "building_bot"
        user.state_data = {"step": "bot_name"}
        db.flush()
        name_part = f", {user.name}" if user.name else ""
        reply = (
            f"Let's build your demo bot{name_part}!\n\n"
            f"What would you like to name it? "
            f"Pick something that fits your brand. (e.g. *Aria*, *Max*, *Sales Bot*)"
        )
        _save_messages(db, user, text, reply)
        db.commit()
        return reply

    if intent == "amend_bot":
        reply = _handle_amendment(db, user, text)
        db.commit()
        return reply

    if intent == "buy_plan" or intent == "pricing":
        if intent == "buy_plan" and not _wants_pay_now(text) and user.demo_count == 0:
            reply = (
                "Happy to help you get started!\n\n"
                "Before you pay anything, I can build you a *free demo bot* in just a few minutes "
                "so you can see exactly what yours would look like.\n\n"
                "Reply *demo* to try it free first, or *pay now* to go straight to checkout."
            )
            _save_messages(db, user, text, reply)
            db.commit()
            return reply
        if intent == "pricing":
            reply = (
                _present_plans()
                + "\n\n💡 *Tip:* You can build and test a *free demo bot* before paying — "
                "just say *build demo* and I'll set one up for you."
            )
            _save_messages(db, user, text, reply)
            db.commit()
            return reply
        user.state = "payment_intent"
        user.state_data = {"collecting": "plan"}
        db.flush()
        reply = _present_plans()
        _save_messages(db, user, text, reply)
        db.commit()
        return reply

    if _wants_pay_now(text):
        user.state = "payment_intent"
        user.state_data = {"collecting": "plan"}
        db.flush()
        reply = _present_plans()
        _save_messages(db, user, text, reply)
        db.commit()
        return reply

    reply = get_joy_response(text, _recent_history(user), state="browsing", state_data=state_data)
    _check_escalation(db, user, text, reply)
    _save_messages(db, user, text, reply)
    db.commit()
    return reply


# ── Bot building ──────────────────────────────────────────────────────────────


def _handle_bot_building(db: Session, user: User, text: str, state_data: dict) -> str:
    step = state_data.get("step", "bot_name")
    collected = {k: v for k, v in state_data.items() if k != "step"}

    if text.lower() in ("cancel", "stop", "quit", "restart"):
        user.state = "browsing"
        user.state_data = {}
        reply = "No problem! Whenever you're ready to build your bot, just say the word."
        _save_messages(db, user, text, reply)
        return reply

    if _wants_to_test(text):
        reply = _handle_test_request(db, user, state_data)
        _save_messages(db, user, text, reply)
        return reply

    if step == "bot_name":
        collected["bot_name"] = text.strip().strip('"\'')
        user.state_data = {"step": "industry", **collected}
        industry_list = "\n".join(
            f"{i+1}. {ind['emoji']} {ind['name']}"
            for i, ind in enumerate(INDUSTRIES)
        )
        reply = (
            f"Love it — *{collected['bot_name']}* it is.\n\n"
            f"What industry is your business in? Reply with the number:\n\n"
            f"{industry_list}"
        )
        _save_messages(db, user, text, reply)
        return reply

    if step == "industry":
        industry_id = parse_industry_choice(text)
        if not industry_id:
            # Accept free-text industry descriptions (e.g. "event management company")
            collected["industry"] = "custom"
            collected["_industry_description"] = text.strip()
            user.state_data = {"step": "business_name", **collected}
            reply = (
                f"Got it — *{text.strip()}*!\n\n"
                f"What's your business or event name?"
            )
            _save_messages(db, user, text, reply)
            return reply
        collected["industry"] = industry_id
        industry = next((i for i in INDUSTRIES if i["id"] == industry_id), None)
        industry_name = industry["name"] if industry else "your industry"
        user.state_data = {"step": "business_name", **collected}
        reply = f"Great choice — {industry_name} bots are very popular!\n\nWhat's your business name?"
        _save_messages(db, user, text, reply)
        return reply

    if step == "business_name":
        collected["business_name"] = text.strip()
        user.state_data = {"step": "business_details", **collected}
        reply = get_industry_detail_prompt(collected.get("industry", "custom"), collected["business_name"])
        _save_messages(db, user, text, reply)
        return reply

    if step == "business_details":
        collected["business_details"] = (collected.get("business_details", "") + "\n" + text).strip()
        done_signals = ("that's all", "thats all", "that's enough", "done", "no more", "for now")
        if _has_enough_for_demo(collected) and (
            any(s in text.lower() for s in done_signals) or len(collected["business_details"]) > 200
        ):
            collected["personality"] = collected.get("personality", "professional")
            user.state_data = {"step": "confirm", **collected}
            reply = (
                _build_confirm_summary(collected)
                + "\n\nReply *yes* to build your free demo, or keep sharing details if you'd like."
            )
        else:
            user.state_data = {"step": "business_details", **collected}
            reply = (
                "Got it — I've noted that down.\n\n"
                "Share anything else the bot should know (or reply *done* when you're ready "
                "and I'll build your free demo)."
            )
        _save_messages(db, user, text, reply)
        return reply

    if step == "personality":
        personality_id = parse_personality_choice(text)
        if not personality_id:
            reply = get_joy_response(
                text, _recent_history(user), state="building_bot",
                state_data={"step": step, "context": "User didn't pick a personality number. Guide them back to choosing (1–6) without repeating the full list.", **collected},
            )
            _save_messages(db, user, text, reply)
            return reply
        collected["personality"] = personality_id
        user.state_data = {"step": "custom_instructions", **collected}
        reply = (
            "Almost done!\n\n"
            "Any special instructions for your bot? "
            "E.g. *'always greet with our tagline'*, *'never mention competitors'*, *'always ask for name first'*.\n\n"
            "Or just reply *skip* if you're good without any special rules."
        )
        _save_messages(db, user, text, reply)
        return reply

    if step == "custom_instructions":
        if text.lower() not in ("skip", "no", "none", "n/a", "nothing"):
            collected["custom_instructions"] = text
        user.state_data = {"step": "confirm", **collected}
        reply = _build_confirm_summary(collected)
        _save_messages(db, user, text, reply)
        return reply

    if step == "confirm":
        yes_words = ("yes", "y", "yeah", "yep", "sure", "ok", "okay", "go ahead",
                     "proceed", "do it", "build it", "build now", "go", "correct",
                     "yh", "yas", "done")
        if any(w in text.lower() for w in yes_words):
            reply = _finalize_bot(db, user, collected)
        else:
            user.state = "browsing"
            user.state_data = {}
            reply = "No problem! Whenever you're ready to try again, just let me know."
        _save_messages(db, user, text, reply)
        return reply

    # Fallback: accumulate conversational input and persist state
    if step in ("business_name", "business_details") or collected.get("bot_name"):
        if step == "business_name":
            collected["business_name"] = text.strip()
            collected["business_details"] = collected.get("business_details", "")
            user.state_data = {"step": "business_details", **collected}
        else:
            collected["business_details"] = (collected.get("business_details", "") + "\n" + text).strip()
            user.state_data = {"step": "business_details", **collected}
        if _has_enough_for_demo(collected):
            reply = (
                "I've captured everything so far.\n\n"
                + _build_confirm_summary(collected)
                + "\n\nReply *yes* to build your free demo now."
            )
            user.state_data = {"step": "confirm", **collected}
        else:
            reply = "Thanks! Tell me a bit more about your business so I can build a useful demo for you."
    else:
        reply = get_joy_response(
            text, _recent_history(user), state="building_bot",
            state_data={
                "step": step,
                "context": (
                    f"Current step: {step}. The demo is FREE — never mention payment. "
                    "Guide the customer through setup or offer to build the demo when ready."
                ),
                **collected,
            },
        )
    _save_messages(db, user, text, reply)
    return reply


def _get_industry_required_info(industry_id: str) -> str:
    requirements = {
        "hotel": "location/address, room types, room rates, amenities, check-in/out times, booking process",
        "restaurant": "location, opening hours, menu highlights, reservation process, delivery options",
        "clinic": "location, services/specialities, appointment booking process, clinic hours",
        "salon": "location, services and prices, booking process, opening hours",
        "real_estate": "areas covered, property types, price ranges, how to book viewings",
        "retail": "product range, pricing, return policy, delivery information",
        "gym": "location, membership types and prices, class schedule, personal training",
        "ecommerce": "product categories, delivery times, refund policy, payment methods",
        "custom": "main services or products, pricing, contact details, location",
    }
    return requirements.get(industry_id, "main services, pricing, and contact details")


def _build_confirm_summary(collected: dict) -> str:
    industry_id = collected.get("industry", "")
    industry = next((i for i in INDUSTRIES if i["id"] == industry_id), None)
    personality_id = collected.get("personality", "professional")
    personality = next((p for p in PERSONALITIES if p["id"] == personality_id), None)
    return (
        f"Here's a summary of your bot:\n\n"
        f"🤖 *Name:* {collected.get('bot_name', '—')}\n"
        f"🏢 *Business:* {collected.get('business_name', '—')}\n"
        f"📂 *Industry:* {industry['name'] if industry else '—'}\n"
        f"✨ *Personality:* {personality['name'] if personality else '—'}\n\n"
        f"Ready to build? Reply *yes* to confirm or *no* to start over."
    )


def _finalize_bot(db: Session, user: User, collected: dict) -> str:
    from app.demo_bot import create_demo_bot
    import os

    order = BotOrder(
        user_id=user.id,
        bot_name=collected.get("bot_name"),
        industry=collected.get("industry"),
        business_name=collected.get("business_name"),
        business_details=collected.get("business_details"),
        personality=collected.get("personality", "professional"),
        tone="friendly",
        custom_instructions=collected.get("custom_instructions"),
        status="completed",
    )
    db.add(order)
    db.flush()

    demo = create_demo_bot(db, order.id)
    base_url = os.getenv("BASE_URL", "https://joy.aicloser.tech")
    demo_link = f"{base_url}/demo/{demo.token}"

    user.state = "browsing"
    user.state_data = {}

    name_part = f", {user.name}" if user.name else ""
    bot_name = collected.get("bot_name", "Your bot")
    biz_name = collected.get("business_name", "your business")

    demos_used = user.demo_count  # after adding current one
    demos_left = MAX_DEMO_BOTS - demos_used
    limit_note = ""
    if demos_left <= 0:
        limit_note = "\n\n_Note: You've used both of your free demo builds._"

    return (
        f"Your demo bot is ready{name_part}! 🎉\n\n"
        f"*{bot_name}* is live for *{biz_name}*.\n\n"
        f"👉 Try it here:\n{demo_link}\n\n"
        f"Active for 7 days. Test it out — if you want to tweak anything, just tell me "
        f"and I'll update it instantly.{limit_note}\n\n"
        f"Happy with it? To get your real bot live on WhatsApp, your website, or Instagram, "
        f"plans start from *$300 setup + $80/month*."
    )


# ── Amendment handler ─────────────────────────────────────────────────────────


def _handle_amendment(db: Session, user: User, text: str) -> str:
    import os
    latest_order = (
        db.query(BotOrder)
        .filter(BotOrder.user_id == user.id, BotOrder.status == "completed")
        .order_by(BotOrder.created_at.desc())
        .first()
    )
    if not latest_order or not latest_order.demo_bot:
        reply = "I don't have a demo bot on file for you yet. Want me to build one now?"
        _save_messages(db, user, text, reply)
        return reply

    current_order = {
        "bot_name": latest_order.bot_name,
        "business_name": latest_order.business_name,
        "business_details": latest_order.business_details,
        "personality": latest_order.personality,
        "custom_instructions": latest_order.custom_instructions,
    }
    changes = parse_bot_amendment(text, current_order)
    if not changes:
        reply = (
            "Could you tell me exactly what you'd like to change? "
            "For example: the bot name, personality, business details, or special instructions."
        )
        _save_messages(db, user, text, reply)
        return reply

    if "bot_name" in changes:
        latest_order.bot_name = changes["bot_name"]
    if "business_name" in changes:
        latest_order.business_name = changes["business_name"]
    if "business_details" in changes:
        latest_order.business_details = changes["business_details"]
    if "personality" in changes:
        latest_order.personality = changes["personality"]
    if "custom_instructions" in changes:
        latest_order.custom_instructions = changes["custom_instructions"]
    db.flush()

    field_labels = {
        "bot_name": "Bot name", "business_name": "Business name",
        "business_details": "Business details", "personality": "Personality",
        "custom_instructions": "Special instructions",
    }
    change_lines = [f"• {field_labels.get(f, f)} → {str(v)[:60]}" for f, v in changes.items()]
    base_url = os.getenv("BASE_URL", "https://joy.aicloser.tech")
    demo_link = f"{base_url}/demo/{latest_order.demo_bot.token}"

    reply = (
        "Done! Here's what I've updated:\n\n"
        + "\n".join(change_lines)
        + f"\n\nYour demo link is the same — changes are live now:\n{demo_link}\n\n"
        "Let me know if you'd like any other tweaks."
    )
    _save_messages(db, user, text, reply)
    return reply


# ── Payment ───────────────────────────────────────────────────────────────────


def _present_plans() -> str:
    return (
        "Here are our current plans:\n\n"
        "1️⃣ *Starter* — $300 setup + $80/month\n"
        "   • 1 Bot — Website Chat Widget\n"
        "   • Custom knowledge base, lead capture, dashboard\n\n"
        "2️⃣ *Growth* ⭐ Most Popular — $700 setup + $150/month\n"
        "   • 1 Bot for WhatsApp, Instagram, or Email\n"
        "   • Everything in Starter + priority support\n\n"
        "3️⃣ *Enterprise* — $1,200 setup + $500/month\n"
        "   • Up to 5 Bots — WhatsApp + Instagram + Email\n"
        "   • Dedicated account manager + strategy calls\n\n"
        "4️⃣ *Business Brain* 🧠 NEW — $1,200 setup + $300/month\n"
        "   • Full AI business intelligence system on WhatsApp\n"
        "   • Customer-facing receptionist + owner/director intelligence\n"
        "   • Staff send reports via WhatsApp → system updates automatically\n"
        "   • Ask about sales, stock, bookings, P&L anytime on WhatsApp\n"
        "   • Integrates with your existing system or we build one for you\n"
        "   • Requires a consultation call — reply *4* to express interest\n\n"
        "Which plan interests you? Reply *1*, *2*, *3*, or *4*."
    )


def _handle_payment_intent(db: Session, user: User, text: str, state_data: dict) -> str:
    if _wants_to_test(text) or text.lower().strip() in ("demo", "try demo", "free demo", "build demo"):
        user.state = "building_bot"
        user.state_data = {"step": "bot_name"}
        reply = (
            "Great idea — let's build your free demo first!\n\n"
            "What would you like to name your bot? "
            "(e.g. *Aria*, *Max*, *We Create*)"
        )
        _save_messages(db, user, text, reply)
        return reply

    collecting = state_data.get("collecting", "plan")

    if collecting == "plan":
        plan_key = text.lower().strip()
        plan = PLAN_MAP.get(plan_key)
        if not plan:
            reply = "Please reply with *1* (Starter), *2* (Growth), *3* (Enterprise), or *4* (Business Brain)."
            _save_messages(db, user, text, reply)
            return reply

        # Business Brain requires consultation — different flow
        if plan.get("requires_consultation"):
            state_data["plan"] = plan
            state_data["collecting"] = "name"
            user.state_data = state_data
            reply = (
                "Great choice — the *Business Brain* is our most powerful product! 🧠\n\n"
                "Since this plan involves integrating with your actual business systems, "
                "our team will need to have a quick consultation with you first to scope everything out.\n\n"
                "Just need a couple of details to get that set up.\n\n"
                "What's your full name?"
            )
            _save_messages(db, user, text, reply)
            return reply
        state_data["plan"] = plan
        state_data["collecting"] = "name"
        user.state_data = state_data
        reply = (
            f"The *{plan['name']}* plan — great choice.\n\n"
            f"Just need a couple of quick details.\n\n"
            f"What's your full name?"
        )

    elif collecting == "name":
        state_data["customer_name"] = text
        if not user.name:
            user.name = text.strip().split()[0].capitalize()
        state_data["collecting"] = "email"
        user.state_data = state_data
        reply = f"Got it, *{text}*. What email address should we reach you on?"

    elif collecting == "email":
        state_data["customer_email"] = text
        state_data["collecting"] = "done"
        user.state_data = state_data

        plan = state_data.get("plan", {})
        lead = PaymentLead(
            user_id=user.id,
            plan=plan.get("name", "Unknown"),
            setup_fee=plan.get("setup_fee", 0),
            monthly_fee=plan.get("monthly_fee", 0),
            customer_name=state_data.get("customer_name"),
            customer_email=text,
            status="new",
            notified=False,
        )
        db.add(lead)
        db.flush()

        # Attempt to generate a Paystack payment link
        payment_link = _generate_payment_link(lead)
        _notify_admin_of_lead(lead)

        plan_name = plan.get("name", "a plan")
        customer_name = state_data.get("customer_name", "there")

        if payment_link:
            reply = (
                f"Perfect! Here's your secure payment link for the *{plan_name}* plan:\n\n"
                f"👉 {payment_link}\n\n"
                f"Once payment goes through, I'll send your login details right away "
                f"and the team will get your bot live on WhatsApp. 🚀"
            )
        else:
            # Fallback if Paystack isn't configured yet
            reply = (
                f"Thank you, *{customer_name}*! 🙏\n\n"
                f"Your *{plan_name}* plan order is in. "
                f"A member of the Closer Tech team will reach out to *{text}* "
                f"within 24 hours to complete your payment and get your bot live.\n\n"
                f"Anything else I can help with in the meantime?"
            )
        user.state = "browsing"
        user.state_data = {}

    else:
        user.state = "browsing"
        user.state_data = {}
        reply = get_joy_response(text, _recent_history(user), state="browsing")

    _save_messages(db, user, text, reply)
    return reply


def _generate_payment_link(lead: PaymentLead) -> str | None:
    """Try to generate a Paystack payment link. Returns None if not configured."""
    import os
    if not os.getenv("PAYSTACK_SECRET_KEY"):
        logger.warning("PAYSTACK_SECRET_KEY not set — skipping payment link generation")
        return None
    try:
        from app.payments import create_payment_link, make_reference
        ref = make_reference(lead.id)
        lead.payment_reference = ref
        url = create_payment_link(
            email=lead.customer_email or "",
            amount_usd=lead.setup_fee,
            reference=ref,
            metadata={
                "lead_id": lead.id,
                "customer_name": lead.customer_name,
                "plan": lead.plan,
            },
        )
        return url
    except Exception as exc:
        logger.error("Failed to create Paystack link: %s", exc)
        return None


def _notify_admin_of_lead(lead: PaymentLead) -> None:
    import os
    import httpx

    admin_number = os.getenv("ADMIN_WHATSAPP_NUMBER")
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

    if not all([admin_number, token, phone_id]):
        logger.warning("Admin notification skipped — credentials missing.")
        return

    message = (
        f"🔔 *New Payment Lead — Closer Tech*\n\n"
        f"👤 Name: {lead.customer_name}\n"
        f"📧 Email: {lead.customer_email}\n"
        f"📦 Plan: {lead.plan}\n"
        f"💰 Setup: ${lead.setup_fee}\n"
        f"📅 Monthly: ${lead.monthly_fee}/mo\n\n"
        f"Check the admin dashboard to follow up."
    )
    try:
        with httpx.Client(timeout=10) as client:
            client.post(
                f"https://graph.facebook.com/v19.0/{phone_id}/messages",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"messaging_product": "whatsapp", "to": admin_number,
                      "type": "text", "text": {"body": message}},
            )
        logger.info("Admin notified of lead %s", lead.id)
    except Exception as exc:
        logger.error("Failed to notify admin: %s", exc)


def create_customer_account(db: Session, user: User, plan: str, email: str) -> CustomerAccount:
    """Create a portal account for a customer after payment."""
    existing = db.query(CustomerAccount).filter(CustomerAccount.user_id == user.id).first()
    if existing:
        return existing

    raw_password = CustomerAccount.generate_password()
    username = (user.name or user.phone).lower().replace(" ", "") + "_ct"
    # Ensure unique username
    base = username
    counter = 1
    while db.query(CustomerAccount).filter(CustomerAccount.username == username).first():
        username = f"{base}{counter}"
        counter += 1

    account = CustomerAccount(
        user_id=user.id,
        username=username,
        password_hash=CustomerAccount.hash_password(raw_password),
        email=email,
        plan=plan,
    )
    db.add(account)
    db.flush()
    account._plain_password = raw_password  # transient, used to send to customer
    return account
