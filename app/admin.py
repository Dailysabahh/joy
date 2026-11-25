"""
Admin dashboard routes.
"""
import os
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.db import get_db
from database.models import BotOrder, CustomerAccount, DemoBot, Escalation, Message, PaymentLead, User

router = APIRouter()
security = HTTPBasic()

BASE_DIR = Path(__file__).parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def require_admin(credentials: HTTPBasicCredentials = Depends(security)):
    admin_user = os.getenv("ADMIN_USERNAME", "admin")
    admin_pass = os.getenv("ADMIN_PASSWORD", "changeme")
    correct_user = secrets.compare_digest(credentials.username, admin_user)
    correct_pass = secrets.compare_digest(credentials.password, admin_pass)
    if not (correct_user and correct_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


# ── Overview dashboard ────────────────────────────────────────────────────────

@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_index(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    total_users       = db.query(func.count(User.id)).scalar()
    total_messages    = db.query(func.count(Message.id)).scalar()
    total_demos       = db.query(func.count(DemoBot.id)).scalar()
    total_leads       = db.query(func.count(PaymentLead.id)).scalar()
    new_leads         = db.query(func.count(PaymentLead.id)).filter(PaymentLead.status == "new").scalar()
    paid_count        = db.query(func.count(PaymentLead.id)).filter(PaymentLead.status == "paid").scalar()
    total_escalations = db.query(func.count(Escalation.id)).scalar()
    open_escalations  = db.query(func.count(Escalation.id)).filter(Escalation.resolved == False).scalar()
    needs_action      = db.query(func.count(PaymentLead.id)).filter(PaymentLead.status == "paid").scalar()

    recent_users = db.query(User).order_by(User.last_active.desc()).limit(10).all()
    recent_leads = db.query(PaymentLead).order_by(PaymentLead.created_at.desc()).limit(5).all()
    recent_escalations = db.query(Escalation).order_by(Escalation.created_at.desc()).limit(5).all()

    base_url = os.getenv("BASE_URL", "")
    return templates.TemplateResponse("admin/index.html", {
        "request": request,
        "stats": {
            "total_users": total_users,
            "total_messages": total_messages,
            "total_demos": total_demos,
            "total_leads": total_leads,
            "new_leads": new_leads,
            "paid_count": paid_count,
            "total_escalations": total_escalations,
            "open_escalations": open_escalations,
            "needs_action": needs_action,
        },
        "recent_users": recent_users,
        "recent_leads": recent_leads,
        "recent_escalations": recent_escalations,
        "base_url": base_url,
    })


# ── Demo Bots ─────────────────────────────────────────────────────────────────

@router.get("/demos", response_class=HTMLResponse)
async def admin_demos(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    orders = (
        db.query(BotOrder)
        .filter(BotOrder.status == "completed")
        .order_by(BotOrder.created_at.desc())
        .all()
    )
    base_url = os.getenv("BASE_URL", "")
    return templates.TemplateResponse("admin/demos.html", {
        "request": request,
        "orders": orders,
        "base_url": base_url,
    })


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    users = db.query(User).order_by(User.last_active.desc()).all()
    accounts = db.query(CustomerAccount).order_by(CustomerAccount.created_at.desc()).all()
    return templates.TemplateResponse("admin/users.html", {"request": request, "users": users, "accounts": accounts})


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    messages = sorted(user.messages, key=lambda m: m.timestamp)
    bot_orders = sorted(user.bot_orders, key=lambda o: o.created_at, reverse=True)
    payment_leads = sorted(user.payment_leads, key=lambda p: p.created_at, reverse=True)
    escalations = sorted(user.escalations, key=lambda e: e.created_at, reverse=True)

    base_url = os.getenv("BASE_URL", "")
    demos = []
    for order in bot_orders:
        if order.demo_bot:
            demos.append({
                "order": order,
                "demo": order.demo_bot,
                "link": f"{base_url}/demo/{order.demo_bot.token}",
            })

    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request,
        "user": user,
        "messages": messages,
        "bot_orders": bot_orders,
        "demos": demos,
        "payment_leads": payment_leads,
        "escalations": escalations,
    })


# ── Payments ──────────────────────────────────────────────────────────────────

@router.get("/payments", response_class=HTMLResponse)
async def admin_payments(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    leads = db.query(PaymentLead).order_by(PaymentLead.created_at.desc()).all()
    return templates.TemplateResponse("admin/payments.html", {"request": request, "leads": leads})


@router.post("/payments/{lead_id}/update-status")
async def update_lead_status(
    lead_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    form = await request.form()
    new_status = form.get("status", "contacted")
    lead = db.query(PaymentLead).filter(PaymentLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404)
    lead.status = new_status
    lead.notified = True
    db.commit()
    return RedirectResponse(url="/admin/payments", status_code=303)


# ── Needs Action (paid, awaiting WhatsApp link) ───────────────────────────────

@router.get("/actions", response_class=HTMLResponse)
async def admin_actions(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    paid_leads = (
        db.query(PaymentLead)
        .filter(PaymentLead.status.in_(["paid", "account_created"]))
        .order_by(PaymentLead.created_at.desc())
        .all()
    )
    return templates.TemplateResponse("admin/actions.html", {
        "request": request,
        "leads": paid_leads,
    })


@router.post("/actions/{lead_id}/mark-done")
async def mark_action_done(
    lead_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    lead = db.query(PaymentLead).filter(PaymentLead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404)
    lead.status = "converted"
    db.commit()
    return RedirectResponse(url="/admin/actions", status_code=303)


# ── Escalations ───────────────────────────────────────────────────────────────

@router.get("/escalations", response_class=HTMLResponse)
async def admin_escalations(
    request: Request,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    escalations = db.query(Escalation).order_by(Escalation.created_at.desc()).all()
    return templates.TemplateResponse("admin/escalations.html", {
        "request": request,
        "escalations": escalations,
    })


@router.post("/escalations/{esc_id}/resolve")
async def resolve_escalation(
    esc_id: int,
    db: Session = Depends(get_db),
    _: str = Depends(require_admin),
):
    esc = db.query(Escalation).filter(Escalation.id == esc_id).first()
    if not esc:
        raise HTTPException(status_code=404)
    esc.resolved = True
    db.commit()
    return RedirectResponse(url="/admin/escalations", status_code=303)


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    _: str = Depends(require_admin),
):
    return templates.TemplateResponse("admin/settings.html", {
        "request": request,
        "phone_id": os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
        "admin_number": os.getenv("ADMIN_WHATSAPP_NUMBER", ""),
        "base_url": os.getenv("BASE_URL", ""),
    })
