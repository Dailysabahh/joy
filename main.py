"""
Joy — Closer Tech WhatsApp AI Assistant
Main FastAPI application entry point.
"""
import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("joy")

# ── App startup / shutdown ────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    from database.db import init_db
    init_db()
    logger.info("Joy is online. Database initialised.")
    yield
    logger.info("Joy shutting down.")


app = FastAPI(
    title="Joy — Closer Tech AI Assistant",
    version="1.0.0",
    lifespan=lifespan,
)

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ── DB dependency ─────────────────────────────────────────────────────────────
from database.db import get_db  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
#  WHATSAPP WEBHOOK
# ══════════════════════════════════════════════════════════════════════════════


@app.get("/webhook")
async def webhook_verify(request: Request):
    """Meta webhook verification handshake."""
    params = dict(request.query_params)
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "joy_verify_2024")

    if mode == "subscribe" and token == verify_token:
        logger.info("Webhook verified by Meta.")
        return PlainTextResponse(content=challenge, status_code=200)

    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def webhook_receive(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Receive WhatsApp messages from Meta Cloud API."""
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    from app.whatsapp import parse_incoming
    messages = parse_incoming(payload)

    for msg in messages:
        background_tasks.add_task(_process_message, msg["phone"], msg["text"], msg.get("wa_message_id"))

    return {"status": "ok"}


def _process_message(phone: str, text: str, message_id: str | None = None) -> None:
    """Process a single incoming WhatsApp message (runs in background)."""
    from database.db import SessionLocal
    from app.conversation import handle_message
    from app.whatsapp import send_text, send_human_like, mark_read

    db = SessionLocal()
    try:
        if message_id:
            mark_read(message_id)

        reply = handle_message(db, phone, text)
        # Brief natural pause before replying — like a person reading then typing
        time.sleep(1.2)
        send_human_like(phone, reply)
        logger.info("Replied to %s (state handled)", phone[-4:])
    except Exception as exc:
        logger.exception("Error processing message from %s: %s", phone, exc)
        # Send a graceful fallback so the customer isn't left in silence
        try:
            send_human_like(
                phone,
                "I'm sorry, sir/ma — I encountered a brief issue. "
                "Please resend your message and I will attend to you right away.",
            )
        except Exception:
            pass
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════════════
#  DEMO BOT ROUTES
# ══════════════════════════════════════════════════════════════════════════════


class DemoChatRequest(BaseModel):
    message: str
    history: list[dict] = []


@app.get("/demo/{token}", response_class=HTMLResponse)
async def demo_chat_page(token: str, request: Request, db: Session = Depends(get_db)):
    """Serve the demo bot chat UI."""
    from app.demo_bot import get_demo_by_token
    from app.bot_builder import INDUSTRIES

    demo = get_demo_by_token(db, token)
    if not demo or not demo.active:
        return templates.TemplateResponse(
            "demo/chat.html",
            {
                "request": request,
                "expired": True,
                "bot_name": "Demo Bot",
                "token": token,
                "greeting": "",
                "avatar": "🤖",
                "business_name": "",
            },
        )

    if demo.is_expired:
        demo.active = False
        db.commit()
        return templates.TemplateResponse(
            "demo/chat.html",
            {
                "request": request,
                "expired": True,
                "bot_name": demo.order.bot_name or "Demo Bot",
                "token": token,
                "greeting": "",
                "avatar": "🤖",
                "business_name": demo.order.business_name or "",
            },
        )

    order = demo.order
    industry = next((i for i in INDUSTRIES if i["id"] == order.industry), None)
    avatar = industry["emoji"] if industry else "🤖"

    bot_name = order.bot_name or "AI Assistant"
    business_name = order.business_name or "this business"

    greeting = (
        f"Hello! Welcome to {business_name}. I'm {bot_name}. "
        f"How can I help you today?"
    )

    return templates.TemplateResponse(
        "demo/chat.html",
        {
            "request": request,
            "expired": False,
            "token": token,
            "bot_name": bot_name,
            "business_name": business_name,
            "avatar": avatar,
            "greeting": greeting,
        },
    )


@app.post("/demo/{token}/chat")
async def demo_chat_api(token: str, body: DemoChatRequest, db: Session = Depends(get_db)):
    """Chat API endpoint for the demo bot."""
    from app.demo_bot import get_demo_by_token, get_order_dict
    from app.joy_brain import get_demo_bot_response

    demo = get_demo_by_token(db, token)
    if not demo or not demo.active or demo.is_expired:
        return JSONResponse({"reply": "This demo has expired. Visit closertech.ai to get your own live bot!"})

    order_dict = get_order_dict(demo.order)
    try:
        reply = get_demo_bot_response(body.message, body.history, order_dict)
    except Exception as exc:
        logger.error("Demo bot error: %s", exc)
        reply = "I'm sorry, I had a brief issue. Please try again!"

    return {"reply": reply}


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD ROUTES
# ══════════════════════════════════════════════════════════════════════════════

from app.admin import router as admin_router  # noqa: E402
app.include_router(admin_router, prefix="/admin")


# ══════════════════════════════════════════════════════════════════════════════
#  PAYSTACK PAYMENT WEBHOOK
# ══════════════════════════════════════════════════════════════════════════════

@app.post("/webhook/paystack")
async def paystack_webhook(request: Request, db: Session = Depends(get_db)):
    """Receive payment confirmation from Paystack and create customer account."""
    raw_body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    from app.payments import verify_webhook_signature
    if not verify_webhook_signature(raw_body, signature):
        logger.warning("Invalid Paystack webhook signature — ignored")
        raise HTTPException(status_code=400, detail="Invalid signature")

    import json
    data = json.loads(raw_body)
    event = data.get("event")
    logger.info("Paystack event: %s", event)

    if event == "charge.success":
        charge = data["data"]
        reference = charge.get("reference", "")
        customer_email = charge["customer"].get("email", "")

        from database.models import PaymentLead
        lead = db.query(PaymentLead).filter(PaymentLead.payment_reference == reference).first()
        if not lead:
            logger.warning("No PaymentLead found for reference %s", reference)
            return {"status": "ok"}

        lead.status = "paid"
        db.flush()

        # Create customer portal account
        from app.conversation import create_customer_account
        account = create_customer_account(db, lead.user, lead.plan, customer_email or lead.customer_email or "")
        plain_password = getattr(account, "_plain_password", None)

        lead.status = "account_created"
        db.commit()
        logger.info("Account created for lead %s, user %s", lead.id, lead.user.phone)

        # Send WhatsApp confirmation + credentials
        if plain_password:
            _send_payment_confirmation(
                phone=lead.user.phone,
                name=lead.customer_name or lead.user.name or "there",
                plan=lead.plan,
                username=account.username,
                password=plain_password,
                portal_url=os.getenv("BASE_URL", "https://joy.aicloser.tech") + "/portal",
            )

    return {"status": "ok"}


@app.get("/payment/confirm", response_class=HTMLResponse)
async def payment_confirm_page(request: Request):
    """Landing page after Paystack redirects the customer back."""
    params = dict(request.query_params)
    trxref = params.get("trxref", "")
    return templates.TemplateResponse("payment_success.html", {
        "request": request,
        "reference": trxref,
    })


def _send_payment_confirmation(phone: str, name: str, plan: str, username: str, password: str, portal_url: str) -> None:
    from app.whatsapp import send_human_like
    message = (
        f"Your payment is confirmed! 🎉\n\n"
        f"Welcome to Closer Tech, *{name}*. Your *{plan}* plan is now active.\n\n"
        f"Here are your account details:\n"
        f"🔑 *Username:* {username}\n"
        f"🔐 *Password:* {password}\n\n"
        f"Login to your dashboard here:\n{portal_url}\n\n"
        f"Your bot is being set up and will be linked to your WhatsApp shortly. "
        f"We'll notify you as soon as it's live!"
    )
    try:
        send_human_like(phone, message)
        logger.info("Payment confirmation sent to %s", phone[-4:])
    except Exception as exc:
        logger.error("Failed to send payment confirmation: %s", exc)


# ══════════════════════════════════════════════════════════════════════════════
#  CUSTOMER PORTAL
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/portal", response_class=HTMLResponse)
async def portal_login_page(request: Request):
    return templates.TemplateResponse("portal/login.html", {"request": request, "error": None})


@app.post("/portal", response_class=HTMLResponse)
async def portal_login_submit(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    username = form.get("username", "").strip().lower()
    password = form.get("password", "")

    from database.models import CustomerAccount
    account = db.query(CustomerAccount).filter(CustomerAccount.username == username).first()
    if not account or not account.check_password(password):
        return templates.TemplateResponse("portal/login.html", {
            "request": request,
            "error": "Incorrect username or password. Please try again.",
        })

    response = RedirectResponse(url="/app", status_code=303)
    response.set_cookie("closer_portal", account.portal_token, httponly=True, samesite="lax", path="/", max_age=60 * 60 * 24 * 30)
    return response


@app.get("/portal/logout")
async def portal_logout():
    response = RedirectResponse(url="/portal", status_code=303)
    response.delete_cookie("closer_portal", path="/")
    return response


@app.get("/portal/dashboard", response_class=HTMLResponse)
@app.get("/app", response_class=HTMLResponse)
async def portal_dashboard(request: Request, db: Session = Depends(get_db)):
    from app.accounts import account_from_request, can_integrate, days_left, trial_open
    account = account_from_request(request, db)
    if not account:
        return RedirectResponse(url="/portal")

    user = account.user
    bot_orders = sorted(user.bot_orders, key=lambda o: o.created_at, reverse=True)
    payment_leads = sorted(user.payment_leads, key=lambda p: p.created_at, reverse=True)

    base_url = os.getenv("BASE_URL", "")
    demos = []
    for order in bot_orders:
        if order.demo_bot:
            demos.append({
                "order": order,
                "demo": order.demo_bot,
                "link": f"{base_url}/demo/{order.demo_bot.token}",
            })

    from app.voice_agents import agents_for
    voice_agents = agents_for(account.id)
    return templates.TemplateResponse("app/home.html", {
        "request": request,
        "account": account,
        "user": user,
        "bot_orders": bot_orders,
        "payment_leads": payment_leads,
        "demos": demos,
        "voice_agents": voice_agents,
        "trial_open": trial_open(account),
        "days_left": days_left(account),
        "can_talk": (account.access or "paid") != "trial" or trial_open(account),
        "can_integrate": can_integrate(account),
        "base_url": str(request.base_url).rstrip("/"),
        "page": "bots",
    })


def _studio_account(request: Request, db: Session):
    from app.accounts import account_from_request, can_integrate, days_left, trial_open
    from app.voice_agents import agents_for
    account = account_from_request(request, db)
    if not account:
        return None, None
    agents = agents_for(account.id)
    extra = {
        "account": account,
        "voice_agents": agents,
        "trial_open": trial_open(account),
        "days_left": days_left(account),
        "can_talk": (account.access or "paid") != "trial" or trial_open(account),
        "can_integrate": can_integrate(account),
        "base_url": str(request.base_url).rstrip("/"),
    }
    return account, extra


@app.get("/account/me")
async def account_me(request: Request, db: Session = Depends(get_db)):
    from app.accounts import account_from_request
    account = account_from_request(request, db)
    if not account:
        return {"username": None}
    return {"username": account.username}


@app.get("/app/bots/{token}/chat", response_class=HTMLResponse)
async def app_bot_chat(token: str, request: Request, db: Session = Depends(get_db)):
    from app.voice_agents import get_agent
    account, extra = _studio_account(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    agent = get_agent(token)
    if not agent or agent.account_id != account.id:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    if not extra["can_talk"]:
        return RedirectResponse(f"/app/bots/{token}", status_code=303)
    return templates.TemplateResponse("app/live_chat.html", {
        "request": request,
        "page": "bots",
        "agent": agent,
        **extra,
    })


@app.post("/app/bots/{token}/message")
async def app_bot_message(token: str, request: Request, db: Session = Depends(get_db)):
    from app.call_log import add_turn, history_for, open_chat
    from app.text_chat import reply
    from app.voice_agents import get_agent
    account, extra = _studio_account(request, db)
    if not account:
        raise HTTPException(status_code=401, detail="Log in to chat.")
    agent = get_agent(token)
    if not agent or agent.account_id != account.id:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    if not extra["can_talk"]:
        raise HTTPException(status_code=403, detail="The trial has ended, so chatting is paused.")
    body = await request.json()
    text = str(body.get("message") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Write a message first.")
    chat_id = str(body.get("chat_id") or "").strip()
    prior = history_for(chat_id, agent.id) if chat_id else None
    if chat_id and prior is None:
        raise HTTPException(status_code=404, detail="That chat was not found.")
    if not chat_id:
        chat_id = open_chat(agent.token, kind="chat")
        prior = []
    add_turn(chat_id, "caller", text)
    try:
        answer = reply(agent, (prior or []) + [{"role": "caller", "text": text}])
    except Exception as exc:
        logger.exception("Text chat failed")
        raise HTTPException(status_code=502, detail="The assistant could not answer just now.") from exc
    if not answer:
        answer = "I missed that. Could you say it once more?"
    add_turn(chat_id, "assistant", answer)
    return {"reply": answer, "chat_id": chat_id}


@app.get("/app/bots/{token}", response_class=HTMLResponse)
async def app_bot(token: str, request: Request, db: Session = Depends(get_db)):
    from app.studio_profile import function_views, pack_for, profile_of, section_views
    from app.voice_agents import get_agent
    account, extra = _studio_account(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    agent = get_agent(token)
    if not agent or agent.account_id != account.id:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    return templates.TemplateResponse("app/bot.html", {
        "request": request,
        "page": "bots",
        "agent": agent,
        "profile": profile_of(agent),
        "pack": pack_for(agent),
        "sections": section_views(agent),
        "functions": function_views(agent),
        "saved": request.query_params.get("saved") == "1",
        **extra,
    })


@app.post("/app/bots/{token}")
async def app_bot_save(token: str, request: Request, db: Session = Depends(get_db)):
    from app.voice_agents import get_agent, save_studio
    account, _extra = _studio_account(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    agent = get_agent(token)
    if not agent or agent.account_id != account.id:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    form = await request.form()
    save_studio(token, form)
    section = str(form.get("section") or "")
    return RedirectResponse(f"/app/bots/{token}?saved=1#{section}", status_code=303)


@app.get("/app/chats", response_class=HTMLResponse)
async def app_chats(request: Request, db: Session = Depends(get_db), bot: str = ""):
    from app.call_log import chats_for_agents, contacts_for_agents
    from app.voice_agents import get_agent
    account, extra = _studio_account(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    agents = extra["voice_agents"]
    if bot:
        chosen = get_agent(bot)
        agents = [chosen] if chosen and chosen.account_id == account.id else []
    ids = [agent.id for agent in agents]
    chats = chats_for_agents(ids)
    people = {person.id: person.name for person in contacts_for_agents(ids)}
    previews = {}
    for chat in chats:
        caller = next((turn.text for turn in chat.turns if turn.role == "caller"), "")
        previews[chat.id] = (caller[:80] + "…") if len(caller) > 80 else (caller or "No words captured")
    return templates.TemplateResponse("app/chats.html", {
        "request": request,
        "page": "chats",
        "chats": chats,
        "names": {agent.id: agent.name for agent in extra["voice_agents"]},
        "contacts": people,
        "previews": previews,
        **extra,
    })


@app.get("/app/chats/{chat_id}", response_class=HTMLResponse)
async def app_chat(chat_id: str, request: Request, db: Session = Depends(get_db)):
    from app.call_log import chat_for_owner, contact_for_owner
    account, extra = _studio_account(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    ids = [agent.id for agent in extra["voice_agents"]]
    chat = chat_for_owner(chat_id, ids)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    agent = next(item for item in extra["voice_agents"] if item.id == chat.agent_id)
    contact = contact_for_owner(chat.contact_id, ids) if chat.contact_id else None
    return templates.TemplateResponse("app/chat.html", {
        "request": request,
        "page": "chats",
        "chat": chat,
        "agent": agent,
        "contact": contact,
        **extra,
    })


@app.post("/app/chats/{chat_id}/contact")
async def app_chat_contact(chat_id: str, request: Request, db: Session = Depends(get_db)):
    from app.call_log import chat_for_owner, update_contact
    account, extra = _studio_account(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    ids = [agent.id for agent in extra["voice_agents"]]
    chat = chat_for_owner(chat_id, ids)
    if not chat or not chat.contact_id:
        raise HTTPException(status_code=404, detail="Contact not found")
    form = await request.form()
    update_contact(
        chat.contact_id,
        ids,
        str(form.get("name") or ""),
        str(form.get("phone") or ""),
        str(form.get("email") or ""),
        str(form.get("note") or ""),
    )
    return RedirectResponse(f"/app/chats/{chat_id}", status_code=303)


@app.get("/app/contacts", response_class=HTMLResponse)
async def app_contacts(request: Request, db: Session = Depends(get_db)):
    from app.call_log import contacts_for_agents
    account, extra = _studio_account(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    ids = [agent.id for agent in extra["voice_agents"]]
    return templates.TemplateResponse("app/contacts.html", {
        "request": request,
        "page": "contacts",
        "contacts": contacts_for_agents(ids),
        "names": {agent.id: agent.name for agent in extra["voice_agents"]},
        **extra,
    })


@app.get("/app/profile", response_class=HTMLResponse)
async def app_profile(request: Request, db: Session = Depends(get_db)):
    account, extra = _studio_account(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    return templates.TemplateResponse("app/profile.html", {
        "request": request,
        "page": "account",
        "saved": request.query_params.get("saved") == "1",
        **extra,
    })


@app.post("/app/profile")
async def app_profile_save(request: Request, db: Session = Depends(get_db)):
    from app.accounts import account_from_request
    account = account_from_request(request, db)
    if not account:
        return RedirectResponse("/portal", status_code=303)
    form = await request.form()
    account.verification_code = str(form.get("verification_code") or "").strip() or None
    db.commit()
    return RedirectResponse("/app/profile?saved=1", status_code=303)


# ══════════════════════════════════════════════════════════════════════════════
#  HEALTH CHECK
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Joy — Closer Tech AI Assistant"}


@app.get("/")
async def root():
    """Closer Tech marketing site."""
    page = BASE_DIR / "static" / "site" / "index.html"
    return FileResponse(page, media_type="text/html")


# ══════════════════════════════════════════════════════════════════════════════
#  PRINCESS - XTRABRIDES OF LAGOS BOT
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/princess", response_class=HTMLResponse)
@app.get("/demo/princess", response_class=HTMLResponse)
async def princess_chat_page(request: Request):
    """Serve the Princess (XtraBrides of Lagos) chat interface."""
    return templates.TemplateResponse(
        "demo/princess_chat.html",
        {
            "request": request,
            "bot_name": "Princess",
            "business_name": "XtraBrides of Lagos",
            "avatar": "👸",
            "greeting": "Welcome to XtraBrides of Lagos! 👰🏽‍♀️ I'm Princess, your personal assistant. How may I help make your bridal dreams come true today?",
        },
    )


@app.post("/princess/chat")
@app.post("/demo/princess/chat")
async def princess_chat_api(body: DemoChatRequest):
    """Chat API endpoint for Princess bot."""
    from app.princess_brain import get_princess_response
    
    try:
        reply = get_princess_response(body.message, body.history)
        logger.info(f"Princess responded to: {body.message[:50]}...")
        return {"reply": reply}
    except Exception as exc:
        logger.error(f"Princess error: {exc}")
        return JSONResponse(
            status_code=500,
            content={"reply": "I apologize for the brief technical issue. Please contact us at +234 810 618 0911 or xtrabrideslagos@yahoo.com"}
        )


# ══════════════════════════════════════════════════════════════════════════════
#  VOICE CHAT
# ══════════════════════════════════════════════════════════════════════════════

from fastapi import WebSocket  # noqa: E402


@app.get("/voice", response_class=HTMLResponse)
async def voice_page(request: Request):
    """Serve the live voice chat UI for Joy."""
    return templates.TemplateResponse("voice/index.html", {"request": request})


@app.websocket("/voice/ws")
async def voice_websocket(websocket: WebSocket):
    """Real-time voice WebSocket — OpenAI Realtime API proxy."""
    from app.voice import handle_voice_ws
    await handle_voice_ws(websocket)


@app.websocket("/voice/enhanced/ws")
async def voice_enhanced_websocket(
    websocket: WebSocket,
    engine: str = "openai",
    bot_id: str = None
):
    """
    Enhanced voice WebSocket with multiple engine support.
    
    Usage:
    - OpenAI: wss://joy.aicloser.tech/voice/enhanced/ws?engine=openai
    - ElevenLabs: wss://joy.aicloser.tech/voice/enhanced/ws?engine=elevenlabs
    """
    from app.voice_enhanced import handle_voice_ws_enhanced
    from database.db import SessionLocal
    
    # Load bot config if bot_id provided
    bot_config = None
    if bot_id:
        db = SessionLocal()
        try:
            from database.models import BotOrder
            bot_order = db.query(BotOrder).filter(BotOrder.id == int(bot_id)).first()
            if bot_order:
                bot_config = {
                    "worker_id": f"bot_{bot_order.id}",
                    "business_id": bot_order.user.phone,
                    "bot_name": bot_order.bot_name,
                    "business_name": bot_order.business_name,
                    "business_details": bot_order.business_details,
                    "personality_description": bot_order.personality or "Helpful assistant",
                }
        finally:
            db.close()
    
    await handle_voice_ws_enhanced(websocket, engine_type=engine, bot_config=bot_config)


@app.get("/voice/builder", response_class=HTMLResponse)
async def voice_builder_page(request: Request):
    """AI Voice Assistant Builder - Choose your engine."""
    return templates.TemplateResponse("voice/builder.html", {
        "request": request,
        "engines": ["OpenAI Realtime", "ElevenLabs"],
    })


@app.get("/test/elevenlabs", response_class=HTMLResponse)
async def elevenlabs_test_page(request: Request):
    """ElevenLabs voice test page - simple and direct."""
    return templates.TemplateResponse("elevenlabs_test.html", {"request": request})


@app.websocket("/voice/elevenlabs/live")
async def elevenlabs_live_websocket(websocket: WebSocket):
    """Live call that speaks with the ElevenLabs voice."""
    from app.elevenlabs_live import handle_elevenlabs_live
    await handle_elevenlabs_live(websocket)


@app.get("/test/voice", response_class=HTMLResponse)
async def voice_test_simple(request: Request):
    """Simple working voice test with OpenAI Realtime."""
    return templates.TemplateResponse("voice_test_simple.html", {"request": request})


@app.get("/test/gpt-live", response_class=HTMLResponse)
async def gpt_live_page(request: Request):
    """Live speech-to-speech call using GPT Realtime and the Marin voice."""
    return templates.TemplateResponse("gpt_live.html", {"request": request})


@app.websocket("/voice/gpt/live")
async def gpt_live_websocket(websocket: WebSocket):
    """Stream a live GPT voice call."""
    from app.openai_live import handle_openai_live
    await handle_openai_live(websocket)


@app.get("/test/gemini-live", response_class=HTMLResponse)
async def gemini_live_page(request: Request):
    """Live two-way call using Gemini Live and the Kore voice."""
    return templates.TemplateResponse("gemini_live.html", {"request": request})


@app.websocket("/voice/gemini/live")
async def gemini_live_websocket(websocket: WebSocket):
    """Stream a live Gemini voice call, optionally for a saved agent."""
    from app.gemini_live import handle_gemini_live
    from app.voice_agents import get_agent, greeting_for, instructions_for

    token = websocket.query_params.get("agent")
    if token:
        agent = get_agent(token)
        if not agent:
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "That voice agent was not found."})
            await websocket.close()
            return
        await handle_gemini_live(
            websocket,
            instructions_for(agent),
            greeting_for(agent),
            voice=getattr(agent, "voice", None),
            agent_token=agent.token,
        )
        return
    await handle_gemini_live(websocket)


@app.get("/voice/widget.js")
async def voice_widget_js():
    """Call button for the Closer Tech site and for customer websites."""
    return FileResponse(BASE_DIR / "static" / "joy-widget.js", media_type="application/javascript")


@app.get("/voice/agents/{token}")
async def voice_agent_card(token: str):
    from app.voice_agents import get_agent
    agent = get_agent(token)
    if not agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    return {"name": agent.name, "business": agent.business_name}


@app.get("/studio", response_class=HTMLResponse)
async def studio_page(request: Request):
    return templates.TemplateResponse("studio.html", {"request": request, "error": None})


@app.get("/studio/voices")
async def studio_voices():
    from app.gemini_voices import catalog
    return catalog()


@app.get("/studio/voice-picker.js")
async def studio_voice_picker_js():
    return FileResponse(BASE_DIR / "static" / "voice-picker.js", media_type="application/javascript")


@app.post("/studio/voices/preview")
async def studio_voice_preview(request: Request):
    from app.gemini_voices import preview_wav
    body = await request.json()
    try:
        audio = await preview_wav(str(body.get("voice") or ""))
    except Exception as exc:
        logger.exception("Voice preview failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=audio, media_type="audio/wav")


@app.post("/studio/research")
async def studio_research(request: Request):
    from app.business_research import research_business
    body = await request.json()
    try:
        return research_business(
            str(body.get("description") or ""),
            str(body.get("website") or ""),
        )
    except Exception as exc:
        logger.exception("Business research failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _portal_cookie(response: RedirectResponse, token: str) -> RedirectResponse:
    response.set_cookie("closer_portal", token, httponly=True, samesite="lax", path="/", max_age=60 * 60 * 24 * 30)
    return response


@app.get("/account/signup", response_class=HTMLResponse)
async def signup_page(request: Request, db: Session = Depends(get_db), bot: str = ""):
    from app.accounts import account_from_request
    from app.voice_agents import claim_agent
    account = account_from_request(request, db)
    if account:
        if bot:
            claim_agent(bot, account.id)
        dest = "/plans" if (account.access or "new") == "new" else "/app"
        if bot and dest == "/plans":
            dest = f"/plans?bot={bot}"
        return RedirectResponse(dest, status_code=303)
    return templates.TemplateResponse("signup.html", {"request": request, "error": None, "bot": bot, "username": "", "email": ""})


@app.post("/account/signup", response_class=HTMLResponse)
async def signup_submit(request: Request, db: Session = Depends(get_db)):
    from app.accounts import register
    from app.voice_agents import claim_agent
    form = await request.form()
    bot = str(form.get("bot") or "").strip()
    username = str(form.get("username") or "")
    email = str(form.get("email") or "")
    password = str(form.get("password") or "")
    confirm = str(form.get("password_confirm") or "")
    try:
        account = register(db, username, password, email, confirm)
    except ValueError as exc:
        return templates.TemplateResponse(
            "signup.html",
            {
                "request": request,
                "error": str(exc),
                "bot": bot,
                "username": username.strip().lower(),
                "email": email.strip().lower(),
            },
            status_code=400,
        )
    if bot:
        claim_agent(bot, account.id)
    dest = f"/plans?bot={bot}" if bot else "/plans"
    return _portal_cookie(RedirectResponse(dest, status_code=303), account.portal_token)


@app.get("/plans", response_class=HTMLResponse)
async def plans_page(request: Request, db: Session = Depends(get_db), bot: str = ""):
    from app.accounts import account_from_request
    from app.voice_agents import get_agent
    account = account_from_request(request, db)
    if not account:
        dest = f"/account/signup?bot={bot}" if bot else "/account/signup"
        return RedirectResponse(dest, status_code=303)
    if (account.access or "new") != "new":
        return RedirectResponse("/app", status_code=303)
    agent = get_agent(bot) if bot else None
    return templates.TemplateResponse("plans.html", {"request": request, "account": account, "agent": agent, "bot": bot})


@app.post("/plans/trial")
async def plans_trial(request: Request, db: Session = Depends(get_db)):
    from app.accounts import account_from_request, start_trial
    from app.voice_agents import claim_agent
    account = account_from_request(request, db)
    if not account:
        return RedirectResponse("/account/signup", status_code=303)
    form = await request.form()
    bot = str(form.get("bot") or "").strip()
    if (account.access or "new") == "new":
        start_trial(db, account, str(form.get("plan") or "starter"))
    if bot:
        claim_agent(bot, account.id)
    return RedirectResponse("/app", status_code=303)


@app.get("/talk/{token}", response_class=HTMLResponse)
async def talk_page(token: str, request: Request, db: Session = Depends(get_db)):
    from app.accounts import account_from_request
    from app.voice_agents import get_agent
    agent = get_agent(token)
    if not agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    account = account_from_request(request, db)
    saved = bool(account and agent.account_id == account.id)
    return templates.TemplateResponse("talk.html", {"request": request, "agent": agent, "saved": saved})


@app.post("/studio")
async def studio_create(request: Request, db: Session = Depends(get_db)):
    from app.accounts import account_from_request
    from app.voice_agents import create_agent
    form = await request.form()
    name = str(form.get("name") or "").strip()
    business_name = str(form.get("business_name") or "").strip()
    description = str(form.get("description") or "").strip()
    greeting = str(form.get("greeting") or "").strip()
    role = str(form.get("role") or "").strip()
    industry = str(form.get("industry") or "").strip()
    website = str(form.get("website") or "").strip()
    objective = str(form.get("objective") or "").strip()
    if not greeting and name and business_name:
        greeting = f"Hello, this is {name} at {business_name}. How can I help?"
    if not name or not business_name or not description:
        return templates.TemplateResponse(
            "studio.html",
            {"request": request, "error": "The assistant needs a name, a business, and what it should know."},
            status_code=400,
        )
    account = account_from_request(request, db)
    agent = create_agent(
        name, business_name, description, greeting, "website", None,
        role=role, industry=industry, website=website, objective=objective,
        voice=str(form.get("voice") or ""),
        tone=str(form.get("tone") or ""),
        manner=str(form.get("manner") or ""),
        account_id=account.id if account else None,
    )
    return RedirectResponse(f"/talk/{agent.token}", status_code=303)


@app.get("/studio/{token}", response_class=HTMLResponse)
async def studio_agent(token: str):
    return RedirectResponse(f"/talk/{token}", status_code=303)


@app.post("/studio/{token}/details")
async def studio_details(token: str, request: Request):
    from app.voice_agents import update_agent
    form = await request.form()
    name = str(form.get("name") or "").strip()
    business_name = str(form.get("business_name") or "").strip()
    description = str(form.get("description") or "").strip()
    greeting = str(form.get("greeting") or "").strip()
    if not name or not business_name or not description or not greeting:
        raise HTTPException(status_code=400, detail="Name, business, knowledge, and opening line are required")
    agent = update_agent(
        token,
        name=name,
        business_name=business_name,
        description=description,
        greeting=greeting,
        role=str(form.get("role") or ""),
        industry=str(form.get("industry") or ""),
        website=str(form.get("website") or ""),
        objective=str(form.get("objective") or ""),
        phone_number=str(form.get("phone_number") or ""),
        voice=str(form.get("voice") or ""),
        tone=str(form.get("tone") or ""),
        manner=str(form.get("manner") or ""),
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    return RedirectResponse(f"/studio/{agent.token}?saved=1", status_code=303)


@app.post("/studio/{token}/phone")
async def studio_phone(token: str, request: Request):
    from app.voice_agents import update_phone
    form = await request.form()
    phone_number = str(form.get("phone_number") or "").strip()
    if not phone_number:
        raise HTTPException(status_code=400, detail="Phone number is required")
    agent = update_phone(token, phone_number)
    if not agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")
    return RedirectResponse(f"/studio/{agent.token}?saved=1", status_code=303)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
